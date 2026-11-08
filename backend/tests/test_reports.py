"""Report reads through real sessions and migrations; attempt rows are test fixtures."""

from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect, dump
from app.main import create_app
from app.scoring import MODEL_VERSION
from test_scoring import attempt_fixture, score

PASSWORD = "report-test-only-password-2026"


class ReportTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="skillproof-reports-")
        self.addCleanup(directory.cleanup)
        self.settings = Settings(
            database_path=Path(directory.name) / "test.sqlite",
            environment="development", cookie_secure=False,
            allowed_hosts=("testserver",),
        )
        self.app = create_app(self.settings)
        self.client = self.enterContext(TestClient(self.app))
        self.auth = self.register(self.client, "owner@example.invalid")
        self.attempt = attempt_fixture()
        self.report = score(self.attempt)
        self.insert_attempt("attempt-1", "submitted", dump(self.report))
        self.insert_attempt("active", "in_progress", None)
        self.insert_attempt("broken", "submitted", "not json")

    def register(self, client, email):
        response = client.post("/api/auth/register", json={
            "email": email, "name": "报告测试用户", "password": PASSWORD,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def insert_attempt(self, attempt_id, status, report_json):
        # Fixtures satisfy the production schema but do not exercise T06 submission.
        with closing(connect(self.settings)) as con:
            con.execute(
                """INSERT INTO attempts(
                    id,user_id,role_id,role_name,status,created_at,submitted_at,
                    blueprint_version,model_version,questions_json,role_json,
                    resources_json,answers_json,report_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (attempt_id, self.auth["user"]["id"], "backend", "后端开发", status,
                 self.attempt["createdAt"], self.report["submittedAt"] if status == "submitted" else None,
                 "test-fixture-v1", MODEL_VERSION, dump(self.attempt["questions"]),
                 dump(self.attempt["role"]), "[]", dump(self.attempt["answers"]), report_json),
            )

    def test_owner_gets_saved_report_with_no_cache_or_private_fields(self):
        response = self.client.get("/api/reports/attempt-1")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), self.report)
        self.assertEqual(response.headers["cache-control"], "no-store")
        for field in ("questions", "answers", "password_hash", "user_id"):
            self.assertNotIn(field, response.json())

    def test_snapshot_survives_question_and_attempt_source_changes(self):
        with closing(connect(self.settings)) as con:
            con.execute("UPDATE questions SET content_json='{}',version=version+1")
            con.execute("""UPDATE attempts SET questions_json='[]',answers_json='{}',
                role_json='{}' WHERE id='attempt-1'""")
        self.assertEqual(self.client.get("/api/reports/attempt-1").json(), self.report)

    def test_saved_report_survives_app_restart_and_real_login(self):
        with TestClient(create_app(self.settings)) as restarted:
            response = restarted.post("/api/auth/login", json={
                "email": "owner@example.invalid", "password": PASSWORD,
            })
            self.assertEqual(response.status_code, 200, response.text)
            result = restarted.get("/api/reports/attempt-1")
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json(), self.report)

    def test_missing_and_sql_injection_are_404(self):
        for attempt_id in ("missing", "' OR 1=1 --"):
            response = self.client.get(f"/api/reports/{attempt_id}")
            self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(response.json(), {"detail": "测评不存在"})

    def test_other_user_cannot_read_even_with_forged_owner_identity(self):
        with TestClient(self.app) as other:
            self.register(other, "other@example.invalid")
            for attempt_id in ("attempt-1", "active", "broken", "missing"):
                response = other.get(f"/api/reports/{attempt_id}",
                    params={"user_id": self.auth["user"]["id"]},
                    headers={"X-User-ID": self.auth["user"]["id"]})
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual(response.json(), {"detail": "测评不存在"})

    def test_unsubmitted_is_409(self):
        response = self.client.get("/api/reports/active")
        self.assertEqual(response.status_code, 409, response.text)

    def test_anonymous_and_forged_cookie_cannot_read(self):
        self.client.cookies.clear()
        for attempt_id in ("attempt-1", "active", "missing"):
            response = self.client.get(f"/api/reports/{attempt_id}",
                params={"user_id": self.auth["user"]["id"]},
                headers={"X-User-ID": self.auth["user"]["id"]})
            self.assertEqual(response.status_code, 401, response.text)
        self.client.cookies.set(self.settings.cookie_name, self.auth["user"]["id"])
        self.assertEqual(self.client.get("/api/reports/attempt-1").status_code, 401)

    def test_expired_session_cannot_read(self):
        with closing(connect(self.settings)) as con:
            con.execute("UPDATE sessions SET expires_at=0")
        self.assertEqual(self.client.get("/api/reports/attempt-1").status_code, 401)

    def test_logout_revokes_report_access_even_if_cookie_is_replayed(self):
        cookie = self.client.cookies.get(self.settings.cookie_name)
        result = self.client.post("/api/auth/logout", headers={"X-CSRF-Token": self.auth["csrfToken"]})
        self.assertEqual(result.status_code, 200, result.text)
        self.client.cookies.set(self.settings.cookie_name, cookie)
        self.assertEqual(self.client.get("/api/reports/attempt-1").status_code, 401)

    def test_corrupt_snapshot_fails_without_leaking_content(self):
        for payload in ("not json", "null", "[]", dump({"id": "wrong-id"})):
            with self.subTest(payload=payload):
                with closing(connect(self.settings)) as con:
                    con.execute("UPDATE attempts SET report_json=? WHERE id='broken'", (payload,))
                response = self.client.get("/api/reports/broken")
                self.assertEqual(response.status_code, 500, response.text)
                self.assertEqual(response.json(), {"detail": "结果快照无效"})

    def test_unavailable_storage_returns_safe_503(self):
        with closing(connect(self.settings)) as con:
            con.execute("ALTER TABLE attempts RENAME TO unavailable_attempts")
        response = self.client.get("/api/reports/attempt-1")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json(), {"detail": "数据服务暂时不可用，请稍后重试"})

    def test_health_still_works(self):
        self.assertEqual(self.client.get("/api/health").json(), {"Status": "ok"})
