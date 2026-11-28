"""Issue #68: exercise released content through real loading, sampling and scoring.

Only the random picker is controlled; authentication, SQLite, routes and scoring
are real. All bank edits and corruption experiments use disposable copies.
"""

import hashlib
import json
import shutil
import unittest
from collections import Counter
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api_assessments import sample_questions
from app.catalog import DIMENSION_IDS, ROLE_MAP
from app.config import Settings
from app.db import connect, dump, initialize
from app.main import create_app

CONTENT = Path(__file__).resolve().parents[1] / "app" / "content"
ROLES = ("backend", "frontend", "algorithm", "qa")


class QuestionBankCompatibilityTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.content = root / "content"
        shutil.copytree(CONTENT, self.content)
        self.questions = json.loads((self.content / "questions.json").read_text(encoding="utf-8"))
        self.manifest = json.loads((self.content / "manifest.json").read_text(encoding="utf-8"))
        self.by_id = {q["id"]: q for q in self.questions}
        self.new_ids = set()
        for batch in self.manifest["importBatches"]:
            if batch["id"].startswith("issue-64-"):
                self.new_ids.update(batch.get("questionIds", []))
                self.new_ids.update(q["questionId"] for q in batch.get("questions", []))
        self.assertTrue(self.new_ids)
        self.assertTrue(self.new_ids <= self.by_id.keys())
        self.settings = Settings(
            database_path=root / "compatibility.sqlite3", content_dir=self.content,
            environment="development", cookie_secure=False,
            allowed_hosts=("testserver",), origin="http://testserver",
        )

    def client(self):
        return TestClient(create_app(self.settings), headers={"Origin": "http://testserver"})

    def register(self, client):
        response = client.post("/api/auth/register", json={
            "email": "compatibility@example.invalid", "name": "题库兼容测试",
            "password": "compatibility-password-2026",
        })
        self.assertEqual(response.status_code, 201, response.text)
        return {"X-CSRF-Token": response.json()["csrfToken"]}

    def picker(self, target=None):
        # Preserve the real candidate list and quota; only replace entropy.
        def choose(population, count):
            return sorted(population, key=lambda q: (
                q["id"] != target, q["id"] not in self.new_ids,
                q["type"] != "multiple", q["id"],
            ))[:count]
        return patch("app.api_assessments.random.SystemRandom.sample", side_effect=choose)

    def create(self, client, headers, role):
        with self.picker():
            response = client.post("/api/attempts", json={"roleId": role}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def snapshot(self, attempt):
        with closing(connect(self.settings)) as con:
            return json.loads(con.execute("SELECT questions_json FROM attempts WHERE id=?",
                                          (attempt["id"],)).fetchone()[0])

    def finish(self, client, headers, attempt, answers):
        url = f"/api/attempts/{attempt['id']}"
        saved = client.put(f"{url}/answers", headers=headers, json={
            "answers": answers, "expectedVersion": attempt["answersVersion"],
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        restored = client.get(url)
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["answers"], {k: sorted(v) for k, v in answers.items()})
        response = client.post(f"{url}/submit", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        queried = client.get(f"/api/reports/{attempt['id']}")
        self.assertEqual(queried.status_code, 200, queried.text)
        self.assertEqual(queried.json(), report)
        return report

    def assert_blueprint(self, questions, role):
        self.assertEqual(len(questions), 18)
        self.assertEqual(len({q["id"] for q in questions}), 18)
        self.assertEqual(Counter((q["dimension"], q["difficulty"]) for q in questions),
                         Counter({(d, level): n for d in DIMENSION_IDS
                                  for level, n in (("easy", 2), ("medium", 1))}))
        for q in questions:
            self.assertEqual(q["status"], "published")
            if ROLE_MAP[role]["topicIds"] is not None:
                self.assertIn(q["topicId"], ROLE_MAP[role]["topicIds"][q["dimension"]])

    def test_released_old_and_imported_metadata_survive_loading(self):
        initialize(self.settings)
        tree = json.loads((self.content / "ability-tree.json").read_text(encoding="utf-8"))
        topics = {d["id"]: {t["id"] for t in d["topics"]} for d in tree["dimensions"]}
        with closing(connect(self.settings)) as con:
            stored = {r["id"]: json.loads(r["content_json"]) for r in con.execute("SELECT * FROM questions")}
        self.assertEqual(set(stored), set(self.by_id))
        self.assertTrue(set(stored) - self.new_ids)
        self.assertEqual(len(stored), self.manifest["questionCount"])
        for qid, source in self.by_id.items():
            with self.subTest(question=qid):
                for field in ("dimension", "topicId", "topic", "difficulty", "type"):
                    self.assertEqual(stored[qid][field], source[field])
                self.assertIn(source["topicId"], topics[source["dimension"]])

    def test_imported_single_and_multiple_are_reachable_in_each_dimension(self):
        initialize(self.settings)
        with closing(connect(self.settings)) as con:
            for dimension in DIMENSION_IDS:
                for kind in ("single", "multiple"):
                    with self.subTest(dimension=dimension, kind=kind):
                        candidates = [q for q in self.questions if q["id"] in self.new_ids
                                      and q["dimension"] == dimension and q["type"] == kind
                                      and q["status"] == "published" and q["difficulty"] in ("easy", "medium")]
                        self.assertTrue(candidates)
                        target = candidates[0]["id"]
                        with self.picker(target):
                            selected, reused = sample_questions(con, "unused-test-user", None)
                        self.assertIn(target, {q["id"] for q in selected})
                        self.assertEqual(reused, 0)
                        self.assert_blueprint(selected, "backend")

    def test_four_roles_real_bank_mixed_answers_and_history(self):
        with self.client() as client:
            headers = self.register(client)
            reports = {}
            for role in ROLES:
                with self.subTest(role=role):
                    attempt = self.create(client, headers, role)
                    self.assertEqual(attempt["roleId"], role)
                    questions = self.snapshot(attempt)
                    self.assert_blueprint(questions, role)
                    for public in attempt["questions"]:
                        self.assertEqual(set(public), {"id", "dimension", "type", "stem", "options"})
                        self.assertEqual(public["stem"], self.by_id[public["id"]]["stem"])
                        self.assertEqual(public["options"], self.by_id[public["id"]]["options"])
                    if role == "backend":
                        for kind in ("single", "multiple"):
                            self.assertTrue(any(q["id"] in self.new_ids and q["type"] == kind for q in questions))
                    answers = {}
                    for q in questions:
                        # Easy questions and all programming questions correct.
                        if q["difficulty"] == "easy" or q["dimension"] == "programming":
                            answers[q["id"]] = list(reversed(q["correct"]))
                        elif q["type"] == "multiple":
                            answers[q["id"]] = q["correct"][:1]  # nonempty partial set earns zero
                        else:
                            answers[q["id"]] = [next(o["id"] for o in q["options"] if o["id"] not in q["correct"])]
                    report = self.finish(client, headers, attempt, answers)
                    # Independent oracle: 14/24 for backend; 50 + programming weight / 2 otherwise.
                    expected = 58.33 if role == "backend" else 50 + ROLE_MAP[role]["weights"]["programming"] / 2
                    self.assertEqual(report["score"], expected)
                    self.assertEqual(report["correctCount"], 13)
                    self.assertEqual({d["id"]: d["score"] for d in report["dimensions"]},
                                     {d: 100 if d == "programming" else 66.67 for d in DIMENSION_IDS})
                    reports[attempt["id"]] = report
            history = client.get("/api/attempts/history")
            self.assertEqual(history.status_code, 200, history.text)
            self.assertEqual({r["roleId"] for r in history.json()["items"]}, set(ROLES))
            for aid, report in reports.items():
                self.assertEqual(client.get(f"/api/reports/{aid}").json(), report)

    def test_missing_role_quota_returns_error_without_partial_attempt(self):
        with self.client() as client:
            headers = self.register(client)
            with closing(connect(self.settings)) as con:
                ids = [q["id"] for q in self.questions if q["dimension"] == "programming"
                       and q["difficulty"] == "medium"
                       and q["topicId"] in ROLE_MAP["frontend"]["topicIds"]["programming"]]
                self.assertTrue(ids)
                con.executemany("UPDATE questions SET status='archived' WHERE id=?", [(qid,) for qid in ids])
                response = client.post("/api/attempts", json={"roleId": "frontend"}, headers=headers)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertIn("medium", response.json()["detail"])
                self.assertIn("不足", response.json()["detail"])
                self.assertEqual(con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 0)
                self.assertGreater(con.execute("SELECT COUNT(*) FROM questions WHERE status='published' AND dimension='programming'").fetchone()[0], 0)

    def test_invalid_published_content_returns_clear_error_without_attempt(self):
        with self.client() as client:
            headers = self.register(client)
            with closing(connect(self.settings)) as con:
                qid = next(q["id"] for q in self.questions if q["status"] == "published")
                con.execute("UPDATE questions SET content_json='{}' WHERE id=?", (qid,))
                response = client.post("/api/attempts", json={"roleId": "backend"}, headers=headers)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertIn("题库数据无效", response.json()["detail"])
                self.assertEqual(con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 0)

    def test_bank_upgrade_and_restart_preserve_active_answers_and_reports(self):
        with self.client() as client:
            headers = self.register(client)
            submitted = self.create(client, headers, "backend")
            first_questions = self.snapshot(submitted)
            report = self.finish(client, headers, submitted, {q["id"]: q["correct"] for q in first_questions})
            active = self.create(client, headers, "frontend")
            old_questions = self.snapshot(active)
            old_answers = {q["id"]: q["correct"] for q in old_questions}
            saved = client.put(f"/api/attempts/{active['id']}/answers", headers=headers,
                               json={"answers": old_answers, "expectedVersion": 0})
            self.assertEqual(saved.status_code, 200, saved.text)
            before = saved.json()
        # A real versioned update changes the live answer keys, not just wording.
        for q in self.questions:
            q["version"] += 1
            q["stem"] = "兼容性测试更新：" + q["stem"]
            options = [o["id"] for o in q["options"]]
            wrong = next(o for o in options if o not in q["correct"])
            q["correct"] = [wrong] if q["type"] == "single" else [wrong, q["correct"][0]]
        (self.content / "questions.json").write_text(dump(self.questions), encoding="utf-8")
        major, minor, revision = self.manifest["bankVersion"].split("-", 1)[0].split(".")
        self.manifest["bankVersion"] = f"{major}.{minor}.{int(revision) + 1}"
        self.manifest["files"]["questions.json"] = hashlib.sha256((self.content / "questions.json").read_bytes()).hexdigest()
        (self.content / "manifest.json").write_text(dump(self.manifest), encoding="utf-8")
        with self.client() as client:
            login = client.post("/api/auth/login", json={
                "email": "compatibility@example.invalid", "password": "compatibility-password-2026",
            })
            self.assertEqual(login.status_code, 200, login.text)
            headers = {"X-CSRF-Token": login.json()["csrfToken"]}
            self.assertEqual(client.get(f"/api/attempts/{active['id']}").json(), before)
            self.assertEqual(self.snapshot(active), old_questions)
            self.assertEqual(client.get(f"/api/reports/{submitted['id']}").json(), report)
            response = client.post(f"/api/attempts/{active['id']}/submit", headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["score"], 100)
            fresh = self.create(client, headers, "frontend")
            self.assertTrue(all(q["stem"].startswith("兼容性测试更新：") for q in fresh["questions"]))
            history = client.get("/api/attempts/history").json()["items"]
            versions = {item["id"]: item["questionBankVersion"] for item in history}
            self.assertNotEqual(versions[active["id"]], versions[fresh["id"]])
