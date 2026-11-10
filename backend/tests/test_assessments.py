"""HTTP lifecycle tests with real SQLite sessions and synthetic published questions."""

from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent / "tests"))

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.assessment_dependencies import get_assessment_roles, get_report_builder
from app.catalog import BLUEPRINT, DIMENSION_IDS, ROLE_MAP
from app.config import Settings
from app.db import connect, dump, initialize, now_iso
from app.main import create_app
from app.scoring import ScoringError
from support.question_bank import assessment_questions, write_bank


def report_fixture(attempt, submitted_at):
    """Orchestration fixture, deliberately not a scoring implementation."""
    return {
        "id": attempt["id"], "roleId": attempt["role"]["id"], "roleName": attempt["role"]["name"],
        "createdAt": attempt["createdAt"], "submittedAt": submitted_at,
        "modelVersion": "test-scorer-v1", "score": 100,
        "dimensions": [{"id": key, "name": key, "score": 100} for key in DIMENSION_IDS],
    }


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skillproof-t06-")
        self.addCleanup(temporary.cleanup)
        self.questions = assessment_questions()
        content = write_bank(Path(temporary.name) / "content", self.questions)
        self.settings = Settings(database_path=Path(temporary.name) / "test.db", content_dir=content,
                                 environment="development", cookie_secure=False, origin=None,
                                 allowed_hosts=("testserver",))
        initialize(self.settings)
        self.con = connect(self.settings)
        self.addCleanup(self.con.close)
        for user_id in ("alice", "bob"):
            self.con.execute(
                "INSERT INTO users VALUES(?,?,?,'student',NULL,?,?)",
                (user_id, user_id + "@example.invalid", user_id, "test-placeholder", now_iso()),
            )
            self.con.execute(
                "INSERT INTO sessions VALUES(?,?,?,?,?)",
                (hashlib.sha256((user_id + "-session").encode()).hexdigest(), user_id,
                 user_id + "-csrf", now_iso(), time.time() + 3600),
            )
        self.app = create_app(self.settings)
        self.scorer = Mock(side_effect=report_fixture)
        self.app.dependency_overrides[get_report_builder] = lambda: self.scorer
        self.client = self.enterContext(TestClient(self.app))
        self.client.cookies.set("skillproof_session", "alice-session")
        self.headers = {"X-CSRF-Token": "alice-csrf"}

    def create(self, role="backend"):
        response = self.client.post("/api/attempts", json={"roleId": role}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def save(self, attempt, answers):
        response = self.client.put(f"/api/attempts/{attempt['id']}/answers",
                                   json={"answers": answers, "expectedVersion": attempt["answersVersion"]}, headers=self.headers)
        if response.status_code == 200:
            attempt["answersVersion"] = response.json()["answersVersion"]
        return response

    def submit(self, attempt):
        return self.client.post(f"/api/attempts/{attempt['id']}/submit", headers=self.headers)

    def test_delayed_old_save_cannot_overwrite_new_answers(self):
        attempt = self.create()
        qid = attempt["questions"][0]["id"]
        url = f"/api/attempts/{attempt['id']}/answers"
        newer = self.client.put(url, json={"expectedVersion": 0, "answers": {qid: ["B"]}}, headers=self.headers)
        self.assertEqual(newer.status_code, 200, newer.text)
        older = self.client.put(url, json={"expectedVersion": 0, "answers": {qid: ["A"]}}, headers=self.headers)
        self.assertEqual(older.status_code, 409, older.text)
        self.assertEqual(older.json()["detail"]["code"], "answers_version_conflict")
        restored = self.client.get(f"/api/attempts/{attempt['id']}").json()
        self.assertEqual(restored["answers"], {qid: ["B"]})
        self.assertEqual(restored["answersVersion"], 1)
        self.assertEqual(json.loads(self.row(attempt)["answers_json"]), {qid: ["B"]})

    def complete(self, attempt):
        answers = {q["id"]: q["correct"] for q in json.loads(self.row(attempt)["questions_json"])}
        response = self.save(attempt, answers)
        self.assertEqual(response.status_code, 200, response.text)
        return answers

    def row(self, attempt):
        return self.con.execute("SELECT * FROM attempts WHERE id=?", (attempt["id"],)).fetchone()

    def test_create_uuid_blueprint_and_private_projection(self):
        attempt = self.create()
        UUID(attempt["id"])
        self.assertEqual(attempt["questionCount"], 18)
        self.assertEqual(attempt["answeredCount"], 0)
        self.assertEqual(attempt["status"], "in_progress")
        self.assertEqual(attempt["answers"], {})
        for question in attempt["questions"]:
            self.assertEqual(set(question), {"id", "dimension", "type", "stem", "options"})
            for option in question["options"]:
                self.assertEqual(set(option), {"id", "text"})
        snapshot = json.loads(self.row(attempt)["questions_json"])
        self.assertEqual(len({q["id"] for q in snapshot}), 18)
        self.assertEqual(Counter(q["difficulty"] for q in snapshot), {"easy": 12, "medium": 6})
        self.assertEqual(Counter((q["dimension"], q["difficulty"]) for q in snapshot),
                         {(dim, level): count for dim in DIMENSION_IDS for level, count in (("easy", 2), ("medium", 1))})
        self.assertEqual(self.row(attempt)["blueprint_version"], BLUEPRINT["version"])
        self.assertTrue(all("correct" in q and "topicId" in q for q in snapshot))

    def test_same_role_resumes_existing_attempt(self):
        first = self.create()
        self.save(first, {first["questions"][0]["id"]: ["A"]})
        resumed = self.create()
        self.assertEqual(first["id"], resumed["id"])
        self.assertEqual(resumed["answeredCount"], 1)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 1)

    def test_concurrent_create_returns_one_attempt(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.create(), range(2)))
        self.assertEqual(responses[0]["id"], responses[1]["id"])
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 1)

    def test_unknown_closed_and_client_owned_fields_rejected(self):
        for payload in ({"roleId": "unknown"}, {"roleId": "frontend"},
                        {"roleId": "backend", "userId": "bob"}, {"roleId": "backend", "score": 100}):
            with self.subTest(payload=payload):
                response = self.client.post("/api/attempts", json=payload, headers=self.headers)
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 0)

    def test_different_open_role_conflicts_with_active_attempt(self):
        self.create()
        self.app.dependency_overrides[get_assessment_roles] = lambda: ROLE_MAP
        response = self.client.post("/api/attempts", json={"roleId": "frontend"}, headers=self.headers)
        self.assertEqual(response.status_code, 409)

    def test_drafts_and_archived_never_replace_missing_published_layer(self):
        for status in ("draft", "archived"):
            with self.subTest(status=status):
                self.con.execute("UPDATE questions SET status=? WHERE id=?", (status, "fixture-os-medium-1"))
                response = self.client.post("/api/attempts", json={"roleId": "backend"}, headers=self.headers)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 0)

    def set_bank_status(self, status):
        for question in self.questions:
            content = {**question, "status": status}
            self.con.execute("UPDATE questions SET status=?,content_json=? WHERE id=?",
                             (status, dump(content), question["id"]))

    def test_draft_only_bank_does_not_create_an_attempt(self):
        self.set_bank_status("draft")
        response = self.client.post("/api/attempts", json={"roleId": "backend"}, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 0)

    def test_publishing_draft_bank_makes_blueprint_available(self):
        self.set_bank_status("draft")
        self.assertEqual(self.client.post("/api/attempts", json={"roleId": "backend"},
                                         headers=self.headers).status_code, 503)
        self.set_bank_status("published")
        attempt = self.create()
        snapshot = json.loads(self.row(attempt)["questions_json"])
        self.assertEqual(len({q["id"] for q in snapshot}), 18)
        for dimension in DIMENSION_IDS:
            self.assertEqual(Counter(q["difficulty"] for q in snapshot if q["dimension"] == dimension),
                             {"easy": 2, "medium": 1})

    def test_hard_questions_are_not_selected_by_current_blueprint(self):
        for dimension in DIMENSION_IDS:
            question = next(q.copy() for q in self.questions if q["dimension"] == dimension)
            question.update(id=f"fixture-{dimension}-hard", difficulty="hard")
            self.con.execute("INSERT INTO questions VALUES(?,?,?,?,?,?)",
                             (question["id"], dimension, "published", 1, dump(question), now_iso()))
        attempt = self.create()
        snapshot = json.loads(self.row(attempt)["questions_json"])
        self.assertEqual(Counter(q["difficulty"] for q in snapshot), {"easy": 12, "medium": 6})

    def test_insufficient_easy_candidates_do_not_duplicate_a_question(self):
        self.con.execute("DELETE FROM questions WHERE id='fixture-os-easy-2'")
        response = self.client.post("/api/attempts", json={"roleId": "backend"}, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 0)

    def test_existing_attempt_retains_old_blueprint_and_hard_snapshot(self):
        attempt = self.create()
        legacy = json.loads(self.row(attempt)["questions_json"])
        for dimension in DIMENSION_IDS:
            question = next(q for q in legacy if q["dimension"] == dimension and q["id"].endswith("easy-2"))
            question.update(id=f"legacy-{dimension}-hard", difficulty="hard")
        self.con.execute("UPDATE attempts SET questions_json=?,blueprint_version='2026.1' WHERE id=?",
                         (dump(legacy), attempt["id"]))
        self.con.execute("UPDATE questions SET status='archived'")
        self.assertEqual(self.create()["id"], attempt["id"])
        self.assertEqual(json.loads(self.row(attempt)["questions_json"]), legacy)
        self.complete(attempt)
        self.assertEqual(self.submit(attempt).status_code, 200)
        self.assertEqual(self.row(attempt)["blueprint_version"], "2026.1")
        self.assertEqual(Counter(q["difficulty"] for q in self.scorer.call_args.args[0]["questions"]),
                         {"easy": 6, "medium": 6, "hard": 6})

    def test_malformed_published_question_rejected_atomically(self):
        self.con.execute("UPDATE questions SET content_json='{}' WHERE id='fixture-os-medium-1'")
        response = self.client.post("/api/attempts", json={"roleId": "backend"}, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 0)

    def test_draft_merge_clear_and_recover_in_new_client(self):
        attempt = self.create()
        first = next(q["id"] for q in attempt["questions"] if q["type"] == "single")
        second = next(q["id"] for q in attempt["questions"] if q["type"] == "multiple")
        self.assertEqual(self.save(attempt, {first: ["A"]}).status_code, 200)
        self.assertEqual(self.save(attempt, {second: ["B", "A"]}).json()["answers"], {first: ["A"], second: ["A", "B"]})
        response = self.save(attempt, {first: []})
        self.assertEqual(response.json()["answers"], {second: ["A", "B"]})
        with TestClient(self.app) as other:
            other.cookies.set("skillproof_session", "alice-session")
            restored = other.get(f"/api/attempts/{attempt['id']}").json()
        self.assertEqual(restored["answers"], {second: ["A", "B"]})
        self.assertEqual(restored["answeredCount"], 1)

    def test_invalid_answers_leave_all_saved_answers_unchanged(self):
        attempt = self.create()
        qid = attempt["questions"][0]["id"]
        self.save(attempt, {qid: ["A"]})
        for answers in ({qid: ["A", "B"]}, {qid: ["Z"]}, {qid: ["A", "A"]},
                        {qid: "A"}, {qid: None}, {qid: [], "not-in-attempt": ["A"]}):
            with self.subTest(answers=answers):
                self.assertEqual(self.save(attempt, answers).status_code, 422)
                self.assertEqual(json.loads(self.row(attempt)["answers_json"]), {qid: ["A"]})

    def test_other_user_cannot_read_save_or_submit(self):
        attempt = self.create()
        self.client.cookies.set("skillproof_session", "bob-session")
        self.headers = {"X-CSRF-Token": "bob-csrf"}
        self.assertEqual(self.client.get(f"/api/attempts/{attempt['id']}").status_code, 404)
        self.assertEqual(self.save(attempt, {}).status_code, 404)
        self.assertEqual(self.submit(attempt).status_code, 404)
        self.assertEqual(self.client.get("/api/attempts/missing").status_code, 404)
        self.assertEqual(self.row(attempt)["status"], "in_progress")

    def test_unfinished_submit_preserves_draft_and_never_scores(self):
        attempt = self.create()
        qid = attempt["questions"][0]["id"]
        self.save(attempt, {qid: ["A"]})
        self.assertEqual(self.submit(attempt).status_code, 422)
        row = self.row(attempt)
        self.assertEqual(json.loads(row["answers_json"]), {qid: ["A"]})
        self.assertEqual(row["status"], "in_progress")
        self.assertIsNone(row["submitted_at"])
        self.assertIsNone(row["report_json"])
        self.scorer.assert_not_called()

    def test_complete_submit_persists_report_time_and_model_together(self):
        attempt = self.create()
        self.complete(attempt)
        response = self.submit(attempt)
        self.assertEqual(response.status_code, 200, response.text)
        report, row = response.json(), self.row(attempt)
        self.assertEqual(row["status"], "submitted")
        self.assertEqual(row["submitted_at"], report["submittedAt"])
        self.assertEqual(row["model_version"], report["modelVersion"])
        self.assertEqual(json.loads(row["report_json"]), report)
        snapshot = self.scorer.call_args.args[0]
        self.assertEqual(snapshot["role"], json.loads(row["role_json"]))
        self.assertEqual(snapshot["questions"], json.loads(row["questions_json"]))

    def test_scoring_failure_rolls_back_and_keeps_saved_answers(self):
        attempt = self.create()
        answers = self.complete(attempt)
        self.scorer.side_effect = HTTPException(503, "test scorer unavailable")
        self.assertEqual(self.submit(attempt).status_code, 503)
        row = self.row(attempt)
        self.assertEqual(row["status"], "in_progress")
        self.assertEqual(json.loads(row["answers_json"]), answers)
        self.assertIsNone(row["report_json"])
        self.assertIsNone(row["submitted_at"])

    def test_t07_scoring_error_returns_422_and_preserves_draft(self):
        attempt = self.create()
        answers = self.complete(attempt)
        self.app.dependency_overrides.pop(get_report_builder)

        with patch("app.assessment_dependencies.build_report", side_effect=ScoringError("invalid snapshot")):
            response = self.submit(attempt)
        self.assertEqual(response.status_code, 422)
        row = self.row(attempt)
        self.assertEqual(row["status"], "in_progress")
        self.assertEqual(json.loads(row["answers_json"]), answers)
        self.assertIsNone(row["submitted_at"])
        self.assertIsNone(row["report_json"])

    def test_duplicate_submit_and_post_submit_edit(self):
        attempt = self.create()
        self.complete(attempt)
        first = self.submit(attempt)
        # A retry must work even if the scoring dependency subsequently fails.
        self.scorer.side_effect = HTTPException(503, "should never be called")
        self.assertEqual(self.submit(attempt).json(), first.json())
        self.assertEqual(self.scorer.call_count, 1)
        self.assertEqual(self.save(attempt, {}).status_code, 409)

    def test_concurrent_submit_scores_once(self):
        attempt = self.create()
        self.complete(attempt)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.submit(attempt), range(2)))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(self.scorer.call_count, 1)

    def test_saved_snapshot_survives_current_bank_edits(self):
        attempt = self.create()
        self.complete(attempt)
        before = self.row(attempt)["questions_json"]
        self.con.execute("UPDATE questions SET content_json='{}',status='archived'")
        self.assertEqual(self.client.get(f"/api/attempts/{attempt['id']}").json()["questions"], attempt["questions"])
        self.assertEqual(self.submit(attempt).status_code, 200)
        self.assertEqual(dump(self.scorer.call_args.args[0]["questions"]), before)

    def test_new_attempt_after_submit_preserves_old_report_and_tracks_reuse(self):
        first = self.create()
        self.complete(first)
        report = self.submit(first).json()
        second = self.create()
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(json.loads(self.row(first)["report_json"]), report)
        self.assertEqual(self.row(second)["reused_question_count"], 18)

    def test_unseen_candidates_are_preferred(self):
        first = self.create()
        self.complete(first)
        self.submit(first)
        extra = self.questions[0].copy()
        extra["id"] += "-new"
        self.con.execute("INSERT INTO questions VALUES(?,?,?,?,?,?)",
                         (extra["id"], extra["dimension"], "published", 1, dump(extra), now_iso()))
        second = self.create()
        self.assertIn(extra["id"], {q["id"] for q in second["questions"]})
        self.assertEqual(self.row(second)["reused_question_count"], 17)

    def test_nested_internal_metadata_never_leaks(self):
        attempt = self.create()
        questions = json.loads(self.row(attempt)["questions_json"])
        questions[0]["privateMetadata"] = "secret"
        questions[0]["options"][0]["isCorrect"] = True
        self.con.execute("UPDATE attempts SET questions_json=? WHERE id=?", (dump(questions), attempt["id"]))
        body = self.client.get(f"/api/attempts/{attempt['id']}").json()
        self.assertNotIn("privateMetadata", dump(body))
        self.assertNotIn("isCorrect", dump(body))

    def test_authentication_csrf_and_cross_site_rejection(self):
        for headers in ({}, {"X-CSRF-Token": "wrong"},
                        {**self.headers, "Origin": "https://untrusted.example"},
                        {**self.headers, "Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                response = self.client.post("/api/attempts", json={"roleId": "backend"}, headers=headers)
                self.assertEqual(response.status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/api/attempts", json={"roleId": "backend"}, headers=self.headers).status_code, 401)
        self.client.cookies.set("skillproof_session", "unrecognized")
        self.assertEqual(self.client.get("/api/attempts/missing").status_code, 401)
        self.client.cookies.set("skillproof_session", "alice-session")
        self.con.execute("UPDATE sessions SET expires_at=0 WHERE user_id='alice'")
        self.assertEqual(self.client.get("/api/attempts/missing").status_code, 401)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
