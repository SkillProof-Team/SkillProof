"""T04 integration tests, isolated from the development database."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.config import Settings
from app.db import connect
from app.main import create_app
from app.security import password_matches

PASSWORD = "test-only-password-2026"


class AuthCatalogTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="skillproof-t04-")
        self.addCleanup(temp.cleanup)
        self.settings = Settings(database_path=Path(temp.name) / "test.db", environment="development", cookie_secure=False, origin="http://localhost:5173", allowed_hosts=("testserver", "localhost"))
        self.app = create_app(self.settings)
        self.client = self.enterContext(TestClient(self.app))

    def register(self):
        response = self.client.post("/api/auth/register", json={"email": "demo@example.com", "name": "测试", "password": PASSWORD})
        self.assertEqual(response.status_code, 201, response.text)
        return response

    def test_registration_refresh_and_hash(self):
        response = self.register()
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=strict", response.headers["set-cookie"])
        self.assertNotIn("password", response.text)
        con = connect(self.settings)
        try:
            hashed = con.execute("SELECT password_hash FROM users").fetchone()[0]
            self.assertNotEqual(hashed, PASSWORD)
            self.assertTrue(password_matches(hashed, PASSWORD))
        finally:
            con.close()
        with TestClient(self.app) as refreshed:
            refreshed.cookies.update(self.client.cookies)
            result = refreshed.get("/api/auth/me")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json(), response.json())

    def test_duplicate_email_and_bad_login(self):
        self.register()
        duplicate = self.client.post("/api/auth/register", json={"email": " DEMO@example.com ", "name": "测试", "password": PASSWORD})
        self.assertEqual(duplicate.status_code, 409)
        for email in ("demo@example.com", "missing@example.com"):
            result = self.client.post("/api/auth/login", json={"email": email, "password": "wrong"})
            self.assertEqual(result.status_code, 401)
            self.assertEqual(result.json(), {"detail": "邮箱或密码不正确"})
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "demo@example.com", "password": PASSWORD}).status_code, 200)

    def test_registration_requires_a_visible_name(self):
        payload = {"email": "boundary@example.invalid", "password": PASSWORD}
        for name in ("\u200b", " \u200b ", "\ufeff", "\u0301", "张\u200b三"):
            with self.subTest(name=repr(name)):
                response = self.client.post("/api/auth/register", json={**payload, "name": name})
                self.assertEqual(response.status_code, 422)
                self.assertNotIn("set-cookie", response.headers)
        # The same email must still be available for a valid Unicode name.
        response = self.client.post("/api/auth/register", json={**payload, "name": "张 Jose\u0301"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["name"], "张 Jose\u0301")

    def test_invalid_input_is_safe_and_uniform(self):
        secret = "short-secret"
        result = self.client.post("/api/auth/register", json={"email": "invalid", "name": "测试", "password": secret})
        self.assertEqual(result.status_code, 422)
        self.assertIn("message", result.json()["detail"])
        self.assertNotIn(secret, result.text)
        self.assertNotIn('"input"', result.text)

    def test_anonymous_expired_session_and_logout_revocation(self):
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        auth = self.register().json()
        cookie = self.client.cookies.get(self.settings.cookie_name)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 403)
        self.assertEqual(self.client.post("/api/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code, 403)
        result = self.client.post("/api/auth/logout", headers={"X-CSRF-Token": auth["csrfToken"]})
        self.assertEqual(result.json(), {"ok": True})
        self.client.cookies.set(self.settings.cookie_name, cookie)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        login = self.client.post("/api/auth/login", json={"email": "demo@example.com", "password": PASSWORD})
        self.assertEqual(login.status_code, 200)
        con = connect(self.settings)
        try:
            con.execute("UPDATE sessions SET expires_at=0")
        finally:
            con.close()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_origin_host_and_request_limit(self):
        self.assertEqual(self.client.get("/api/health").json(), {"Status": "ok"})
        for host in ("evil.example", "localhost:bad", "localhost/path"):
            self.assertEqual(self.client.get("/api/health", headers={"Host": host}).status_code, 400)
        for headers in ({"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.client.post("/api/auth/login", json={}, headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/api/auth/login", json={}, headers={"Origin": "http://localhost:5173"}).status_code, 422)
        self.assertEqual(self.client.post("/api/auth/login", content="x" * (self.settings.max_body_bytes + 1)).status_code, 413)

    def test_catalog_matches_t03_and_does_not_expose_questions(self):
        result = self.client.get("/api/catalog")
        self.assertEqual(result.status_code, 200)
        data = result.json()
        tree = json.loads((self.settings.content_dir / "ability-tree.json").read_text(encoding="utf-8"))
        self.assertEqual({r["id"] for r in data["roles"]}, {"backend", "frontend", "algorithm", "qa"})
        self.assertEqual([r["id"] for r in data["roles"] if r["enabled"]], ["backend"])
        backend = next(r for r in data["roles"] if r["id"] == "backend")
        self.assertEqual(backend["description"], tree["role"]["description"])
        self.assertEqual(backend["topics"], {d["id"]: [t["name"] for t in d["topics"]] for d in tree["dimensions"]})
        self.assertEqual(data["dimensions"], [{k: d[k] for k in ("id", "name", "description")} for d in tree["dimensions"]])
        self.assertNotIn('"correct"', result.text)
        self.assertNotIn('"questions"', result.text)
        self.assertEqual(result.headers["cache-control"], "no-store")

    def test_expected_api_routes(self):
        paths = {path for path in self.app.openapi()['paths'] if path.startswith('/api/')}
        self.assertEqual(paths, {"/api/health", "/api/catalog", "/api/auth/register", "/api/auth/login", "/api/auth/logout", "/api/auth/me", "/api/reports/{attempt_id}"})


if __name__ == "__main__":
    unittest.main()
