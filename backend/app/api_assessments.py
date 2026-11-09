"""Owner-scoped assessment creation, draft recovery and atomic submission."""

from collections import defaultdict
import json
import random
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from .assessment_dependencies import get_assessment_roles, get_report_builder, require_assessment_user
from .catalog import BLUEPRINT, DIMENSION_IDS, DIMENSION_NAMES, MODEL_VERSION
from .db import dump, now_iso, transaction
from .models import AnswersInput, AttemptInput, QuestionInput
from .reports import read_report
from .security import get_db

router = APIRouter(prefix="/api", tags=["assessments"])


def owned_attempt(con, attempt_id: str, user_id: str):
    row = con.execute("SELECT * FROM attempts WHERE id=? AND user_id=?", (attempt_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "测评不存在")
    return row


def attempt_view(row) -> dict:
    # Construct nested allowlists; future internal metadata stays private.
    questions = [
        {
            "id": q["id"], "dimension": q["dimension"], "type": q["type"], "stem": q["stem"],
            "options": [{"id": option["id"], "text": option["text"]} for option in q["options"]],
        }
        for q in json.loads(row["questions_json"])
    ]
    answers = json.loads(row["answers_json"])
    return {
        "id": row["id"], "roleId": row["role_id"], "roleName": row["role_name"],
        "status": row["status"], "createdAt": row["created_at"], "submittedAt": row["submitted_at"],
        "questionCount": len(questions), "answeredCount": sum(bool(value) for value in answers.values()),
        "questions": questions, "answers": answers,
    }


def sample_questions(con, user_id: str) -> tuple[list[dict], int]:
    """Apply catalog quotas evenly across dimensions, using published questions."""
    strata = defaultdict(list)
    for row in con.execute("SELECT content_json FROM questions WHERE status='published' ORDER BY id"):
        try:
            question = QuestionInput.model_validate_json(row["content_json"]).model_dump()
        except ValidationError as exc:
            raise HTTPException(503, "已发布题库数据无效，暂时无法创建测评") from exc
        if question["status"] != "published":
            raise HTTPException(503, "题库发布状态不一致，暂时无法创建测评")
        strata[(question["dimension"], question["difficulty"])].append(question)
    seen = {
        question["id"]
        for row in con.execute("SELECT questions_json FROM attempts WHERE user_id=?", (user_id,))
        for question in json.loads(row["questions_json"])
    }
    questions = []
    rng = random.SystemRandom()
    for dimension in DIMENSION_IDS:
        for difficulty, total in BLUEPRINT["difficultyCounts"].items():
            count = total // len(DIMENSION_IDS)
            if count == 0:
                continue
            candidates = strata[(dimension, difficulty)]
            if len(candidates) < count:
                raise HTTPException(503, f"已发布题库中{DIMENSION_NAMES[dimension]}的{difficulty}题不足{count}道，暂时无法创建测评")
            unseen = [q for q in candidates if q["id"] not in seen]
            selected = rng.sample(unseen, min(count, len(unseen)))
            selected_ids = {q["id"] for q in selected}
            remaining = [q for q in candidates if q["id"] not in selected_ids]
            selected.extend(rng.sample(remaining, count - len(selected)))
            questions.extend(selected)
    return questions, sum(q["id"] in seen for q in questions)


@router.post("/attempts")
def start_attempt(
    payload: AttemptInput, user_id: str = Depends(require_assessment_user),
    con=Depends(get_db), roles=Depends(get_assessment_roles),
):
    role = roles.get(payload.roleId)
    if role is None:
        raise HTTPException(422, "该岗位暂未开放测评")
    with transaction(con):
        active = con.execute("SELECT * FROM attempts WHERE user_id=? AND status='in_progress'", (user_id,)).fetchone()
        if active:
            if active["role_id"] != payload.roleId:
                raise HTTPException(409, "请先完成当前测评，再切换岗位")
            return attempt_view(active)
        questions, reused = sample_questions(con, user_id)
        attempt_id = str(uuid4())
        con.execute(
            "INSERT INTO attempts(id,user_id,role_id,role_name,status,created_at,blueprint_version,"
            "model_version,questions_json,role_json,resources_json,reused_question_count) "
            "VALUES(?,?,?,?,'in_progress',?,?,?,?,?,?,?)",
            (attempt_id, user_id, role["id"], role["name"], now_iso(), BLUEPRINT["version"], MODEL_VERSION,
             dump(questions), dump(role), "[]", reused),
        )
        return attempt_view(owned_attempt(con, attempt_id, user_id))


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: str, user_id: str = Depends(require_assessment_user), con=Depends(get_db)):
    return attempt_view(owned_attempt(con, attempt_id, user_id))


@router.put("/attempts/{attempt_id}/answers")
def save_answers(
    attempt_id: str, payload: AnswersInput,
    user_id: str = Depends(require_assessment_user), con=Depends(get_db),
):
    with transaction(con):
        row = owned_attempt(con, attempt_id, user_id)
        if row["status"] != "in_progress":
            raise HTTPException(409, "已提交的测评不可修改")
        questions = {q["id"]: q for q in json.loads(row["questions_json"])}
        answers = json.loads(row["answers_json"])
        for question_id, selected in payload.answers.items():
            if question_id not in questions:
                raise HTTPException(422, "答案包含不属于本次测评的题目")
            question = questions[question_id]
            if question["type"] not in {"single", "multiple"}:
                raise HTTPException(503, "测评题型无效，暂时无法保存答案")
            if question["type"] == "single" and len(selected) > 1:
                raise HTTPException(422, "单选题只能选择一个选项")
            if not set(selected) <= {option["id"] for option in question["options"]}:
                raise HTTPException(422, "答案包含不存在的选项")
            if selected:
                answers[question_id] = sorted(selected)
            else:
                answers.pop(question_id, None)
        con.execute("UPDATE attempts SET answers_json=? WHERE id=? AND user_id=?", (dump(answers), attempt_id, user_id))
        return attempt_view(owned_attempt(con, attempt_id, user_id))


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(
    attempt_id: str, user_id: str = Depends(require_assessment_user),
    con=Depends(get_db), build_report=Depends(get_report_builder),
):
    with transaction(con):
        row = owned_attempt(con, attempt_id, user_id)
        if row["status"] == "submitted":
            return read_report(con, attempt_id, user_id)
        questions = json.loads(row["questions_json"])
        answers = json.loads(row["answers_json"])
        if not questions or any(not answers.get(q["id"]) for q in questions):
            raise HTTPException(422, "请完成全部题目后再提交")
        submitted_at = now_iso()
        report = build_report(
            {"id": row["id"], "questions": questions, "answers": answers,
             "role": json.loads(row["role_json"]), "createdAt": row["created_at"]},
            submitted_at,
        )
        # Persist state, authoritative scoring version, timestamp and report together.
        con.execute(
            "UPDATE attempts SET status='submitted',submitted_at=?,report_json=?,model_version=? "
            "WHERE id=? AND user_id=?",
            (submitted_at, dump(report), report["modelVersion"], attempt_id, user_id),
        )
        return report
