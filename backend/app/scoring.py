"""Pure Alpha scoring of trusted attempt snapshots; no HTTP or database access."""

from fractions import Fraction


DIMENSIONS = (
    ("programming", "程序设计"),
    ("algorithms", "算法基础"),
    ("database", "数据库"),
    ("network", "计算机网络"),
    ("os", "操作系统"),
    ("software", "软件工程"),
)
DIMENSION_IDS = tuple(key for key, _ in DIMENSIONS)
MODEL_VERSION = "alpha-difficulty-1-2-5-v1"
DIFFICULTY_WEIGHTS = {"easy": 1, "medium": 2, "hard": 5}


class ScoringError(ValueError):
    """Invalid or incomplete snapshot/answers; callers must not persist a report."""


def _percentage(correct: int, total: int) -> Fraction:
    return Fraction(correct * 100, total)


def _rounded(value: Fraction) -> float:
    # Exact integer arithmetic, round half up to two decimals.
    scaled = value * 100
    return (scaled.numerator * 2 + scaled.denominator) // (2 * scaled.denominator) / 100


def _options(value: object, label: str) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ScoringError(f"{label}必须是选项 ID 数组")
    if len(set(value)) != len(value):
        raise ScoringError(f"{label}包含重复选项")
    return set(value)


def build_report(attempt: dict, submitted_at: str) -> dict:
    """Score complete server-side snapshots; never accept caller-supplied scores.

    T06 supplies id, role {id, name}, createdAt, questions and answers. Every
    question has id, dimension, type, difficulty, options [{id, text}], and correct [IDs].
    Missing/empty answers are rejected, matching the submit API contract.
    """
    try:
        attempt_id = attempt["id"]
        role_id, role_name = attempt["role"]["id"], attempt["role"]["name"]
        created_at = attempt["createdAt"]
        questions, answers = attempt["questions"], attempt["answers"]
    except (KeyError, TypeError) as exc:
        raise ScoringError("测评快照缺少必要字段") from exc
    if any(not isinstance(value, str) or not value.strip() for value in
           (attempt_id, role_id, role_name, created_at, submitted_at)):
        raise ScoringError("测评标识、岗位和时间必须是非空字符串")
    if not isinstance(questions, list) or not questions or not isinstance(answers, dict):
        raise ScoringError("测评必须包含题目列表和作答字典")

    totals = dict.fromkeys(DIMENSION_IDS, 0)
    correct_counts = dict.fromkeys(DIMENSION_IDS, 0)
    total_weight = 0
    earned_weight = 0
    seen = set()
    for question in questions:
        try:
            question_id, dimension, kind = question["id"], question["dimension"], question["type"]
            raw_options, raw_correct = question["options"], question["correct"]
            difficulty = question["difficulty"]
        except (KeyError, TypeError) as exc:
            raise ScoringError("题目快照缺少必要字段") from exc
        if not isinstance(question_id, str) or not question_id or question_id in seen:
            raise ScoringError("题目 ID 必须非空且唯一")
        seen.add(question_id)
        if not isinstance(dimension, str) or dimension not in totals:
            raise ScoringError("题目包含未知维度")
        if kind not in ("single", "multiple"):
            raise ScoringError("题目类型必须是 single 或 multiple")
        if not isinstance(difficulty, str) or difficulty not in DIFFICULTY_WEIGHTS:
            raise ScoringError("题目难度必须是 easy、medium 或 hard")
        if not isinstance(raw_options, list) or any(not isinstance(o, dict) for o in raw_options):
            raise ScoringError("题目选项格式无效")
        option_ids = _options([o.get("id") for o in raw_options], "题目选项")
        correct = _options(raw_correct, "正确答案")
        if not correct or not correct <= option_ids or (kind == "single" and len(correct) != 1):
            raise ScoringError("题目正确答案无效")
        selected = _options(answers.get(question_id, []), "作答")
        if not selected:
            raise ScoringError("请完成全部题目后再提交")
        if not selected <= option_ids or (kind == "single" and len(selected) != 1):
            raise ScoringError("作答包含无效选项或单选题选择过多")
        totals[dimension] += 1
        correct_counts[dimension] += int(selected == correct)
        weight = DIFFICULTY_WEIGHTS[difficulty]
        total_weight += weight
        if selected == correct:
            earned_weight += weight

    if set(answers) - seen:
        raise ScoringError("答案包含不属于本次测评的题目")
    missing = [key for key in DIMENSION_IDS if not totals[key]]
    if missing:
        raise ScoringError("测评缺少维度题目：" + ", ".join(missing))

    exact = {key: _percentage(correct_counts[key], totals[key]) for key in DIMENSION_IDS}
    dimensions = [
        {"id": key, "name": name, "score": _rounded(exact[key]),
         "correct": correct_counts[key], "total": totals[key]}
        for key, name in DIMENSIONS
    ]
    weak_dimensions = sorted(
        (item.copy() for item in dimensions if exact[item["id"]] < 100),
        key=lambda item: (exact[item["id"]], DIMENSION_IDS.index(item["id"])),
    )
    count = sum(correct_counts.values())
    return {
        "id": attempt_id, "roleId": role_id, "roleName": role_name,
        "createdAt": created_at, "submittedAt": submitted_at,
        "modelVersion": MODEL_VERSION,
        "score": _rounded(_percentage(earned_weight, total_weight)),
        "correctCount": count, "questionCount": len(questions),
        "dimensions": dimensions, "weakDimensions": weak_dimensions,
    }
