from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.reports import require_report_user
from test_scoring import attempt_fixture, score


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name) / "test.sqlite"
        self.report = score(attempt_fixture())
        # Test-only schema representing the minimum proposed T02 contract.
        # This is not the production migration or a real T06 submission.
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE attempts (id TEXT PRIMARY KEY, user_id TEXT, status TEXT, report_json TEXT)")
            connection.executemany("INSERT INTO attempts VALUES (?, ?, ?, ?)", [
                ("attempt-1", "owner", "submitted", json.dumps(self.report)),
                ("active", "owner", "in_progress", None),
                ("broken", "owner", "submitted", "not json"),
            ])
        app.state.report_connection_factory = lambda: sqlite3.connect(self.path, check_same_thread=False)
        app.dependency_overrides[require_report_user] = lambda: "owner"
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        if hasattr(app.state, "report_connection_factory"):
            del app.state.report_connection_factory
        self.directory.cleanup()

    def test_owner_gets_saved_report(self):
        response = self.client.get("/api/reports/attempt-1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.report)

    def test_report_survives_connection_restart_and_question_bank_change(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE questions (id TEXT, correct TEXT)")
            connection.execute("INSERT INTO questions VALUES ('programming-0', 'D')")
        self.assertEqual(self.client.get("/api/reports/attempt-1").json(), self.report)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DROP TABLE questions")
        self.assertEqual(self.client.get("/api/reports/attempt-1").json(), self.report)

    def test_missing_foreign_and_sql_injection_are_404(self):
        self.assertEqual(self.client.get("/api/reports/missing").status_code, 404)
        self.assertEqual(self.client.get("/api/reports/' OR 1=1 --").status_code, 404)
        app.dependency_overrides[require_report_user] = lambda: "other-user"
        response = self.client.get("/api/reports/attempt-1")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "测评不存在"})
        self.assertEqual(self.client.get("/api/reports/active").status_code, 404)

    def test_unsubmitted_is_409(self):
        self.assertEqual(self.client.get("/api/reports/active").status_code, 409)

    def test_sqlite_row_factory_and_connection_cleanup(self):
        opened = []

        def factory():
            connection = sqlite3.connect(self.path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            opened.append(connection)
            return connection

        app.state.report_connection_factory = factory
        for attempt_id, status in [("attempt-1", 200), ("missing", 404), ("active", 409)]:
            self.assertEqual(self.client.get(f"/api/reports/{attempt_id}").status_code, status)
            with self.assertRaises(sqlite3.ProgrammingError):
                opened[-1].execute("SELECT 1")

    def test_missing_auth_cannot_be_bypassed_with_client_identity(self):
        app.dependency_overrides.clear()
        response = self.client.get("/api/reports/attempt-1?user_id=owner", headers={"X-User-ID": "owner"})
        self.assertEqual(response.status_code, 401)

    def test_missing_storage_is_503(self):
        del app.state.report_connection_factory
        self.assertEqual(self.client.get("/api/reports/attempt-1").status_code, 503)

    def test_corrupt_snapshot_fails_without_leaking_content(self):
        response = self.client.get("/api/reports/broken")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "结果快照无效"})

    def test_health_still_works(self):
        self.assertEqual(self.client.get("/api/health").json(), {"Status": "ok"})
