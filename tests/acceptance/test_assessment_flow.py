"""Exercise the assessment and reporting routes with real sessions and scoring."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect, dump, now_iso
from app.main import create_app
from app.scoring import build_report


class AssessmentFlowTests(unittest.TestCase):
    def test_authenticated_submission_lifecycle(self):
        directory = self.enterContext(TemporaryDirectory())
        settings = Settings(
            database_path=Path(directory) / "assessment.sqlite3",
            environment="development", cookie_secure=False,
            origin=None, allowed_hosts=("testserver",),
        )
        app = create_app(settings)
        client = self.enterContext(TestClient(app))
        other = self.enterContext(TestClient(app))
        connection = self.enterContext(closing(connect(settings)))
        seed = json.loads((settings.content_dir / "questions.json").read_text(encoding="utf-8"))
        for question in seed:
            published = {
                **question, "status": "published",
                "sources": [{"title": "Test fixture", "url": "https://example.com/fixture"}],
            }
            connection.execute(
                "UPDATE questions SET status='published', content_json=?, updated_at=? WHERE id=?",
                (dump(published), now_iso(), question["id"]),
            )

        headers = self.login(client, "owner")
        other_headers = self.login(other, "other")
        created = client.post("/api/attempts", json={"roleId": "backend"}, headers=headers)
        self.assertEqual(created.status_code, 200, created.text)
        attempt = created.json()
        attempt_id = attempt["id"]
        url = f"/api/attempts/{attempt_id}"
        report_url = f"/api/reports/{attempt_id}"
        resumed = client.post("/api/attempts", json={"roleId": "backend"}, headers=headers)
        self.assertEqual(resumed.status_code, 200, resumed.text)
        self.assertEqual(resumed.json()["id"], attempt_id)
        self.assertEqual(client.get(report_url).status_code, 409)

        snapshot = connection.execute(
            "SELECT questions_json FROM attempts WHERE id=?", (attempt_id,),
        ).fetchone()["questions_json"]
        questions = json.loads(snapshot)
        self.assertEqual(len(questions), 18)
        answers = {q["id"]: q["correct"] for q in questions}
        saved = client.put(f"{url}/answers", json={"answers": answers}, headers=headers)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(client.get(url).json()["answers"], saved.json()["answers"])

        # A bad stored difficulty triggers the real scorer's validation.
        questions[0]["difficulty"] = "invalid"
        connection.execute("UPDATE attempts SET questions_json=? WHERE id=?", (dump(questions), attempt_id))
        failed = client.post(f"{url}/submit", headers=headers)
        self.assertEqual(failed.status_code, 422, failed.text)
        draft = client.get(url).json()
        self.assertEqual(draft["status"], "in_progress")
        self.assertEqual(draft["answers"], saved.json()["answers"])
        self.assertEqual(client.get(report_url).status_code, 409)
        connection.execute("UPDATE attempts SET questions_json=? WHERE id=?", (snapshot, attempt_id))

        with patch("app.assessment_dependencies.build_report", wraps=build_report) as scorer:
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: client.post(f"{url}/submit", headers=headers), range(2)))
            retry = client.post(f"{url}/submit", headers=headers)
            self.assertEqual(scorer.call_count, 1)
        for response in [*responses, retry]:
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), responses[0].json())
        report = responses[0].json()
        self.assertEqual(report["score"], 100)
        self.assertEqual(report["modelVersion"], "alpha-difficulty-1-2-5-v1")
        self.assertEqual([item["score"] for item in report["dimensions"]], [100] * 6)
        queried = client.get(report_url)
        self.assertEqual(queried.status_code, 200, queried.text)
        self.assertEqual(queried.json(), report)
        self.assertEqual(client.put(f"{url}/answers", json={"answers": {}}, headers=headers).status_code, 409)
        self.assertEqual(other.get(url).status_code, 404)
        self.assertEqual(other.put(f"{url}/answers", json={"answers": {}}, headers=other_headers).status_code, 404)
        self.assertEqual(other.post(f"{url}/submit", headers=other_headers).status_code, 404)
        self.assertEqual(other.get(report_url).status_code, 404)

    def login(self, client, name):
        email = f"{name}@example.com"
        password = "assessment-acceptance-password"
        registered = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
        self.assertEqual(registered.status_code, 201, registered.text)
        logged_in = client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        return {"X-CSRF-Token": logged_in.json()["csrfToken"]}
