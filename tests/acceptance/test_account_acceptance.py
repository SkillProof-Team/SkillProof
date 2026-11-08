"""Account and catalog acceptance through the real API and an isolated database."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


PASSWORD = "acceptance-test-password"


class AccountAcceptanceTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.settings = Settings(
            database_path=Path(directory) / "accounts.sqlite3",
            environment="development",
            cookie_secure=False,
            allowed_hosts=("testserver",),
            origin="http://testserver",
        )

    def client(self):
        return TestClient(create_app(self.settings), headers={"Origin": "http://testserver"})

    def register(self, client, email="qa@example.invalid"):
        response = client.post("/api/auth/register", json={
            "email": email, "name": "验收账号", "password": PASSWORD,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_register_logout_and_login_preserve_identity(self):
        with self.client() as client:
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
            registered = self.register(client)
            user = registered["user"]
            self.assertEqual(user["role"], "student")
            self.assertEqual(set(user), {"id", "email", "name", "role", "targetRole", "createdAt"})
            current = client.get("/api/auth/me")
            self.assertEqual(current.status_code, 200)
            self.assertEqual(current.json()["user"], user)

            logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": registered["csrfToken"]})
            self.assertEqual(logout.status_code, 200, logout.text)
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
            login = client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD})
            self.assertEqual(login.status_code, 200, login.text)
            self.assertEqual(login.json()["user"], user)
            self.assertEqual(client.get("/api/auth/me").json()["user"], user)

    def test_duplicate_registration_and_wrong_password_leave_account_usable(self):
        with self.client() as client:
            original = self.register(client)["user"]
            duplicate = client.post("/api/auth/register", json={
                "email": " QA@EXAMPLE.INVALID ", "name": "替换姓名",
                "password": "different-test-password",
            })
            self.assertEqual(duplicate.status_code, 409)
            client.cookies.clear()
            rejected = client.post("/api/auth/login", json={
                "email": "qa@example.invalid", "password": "different-test-password",
            })
            self.assertEqual(rejected.status_code, 401)
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
            login = client.post("/api/auth/login", json={
                "email": "QA@EXAMPLE.INVALID", "password": PASSWORD,
            })
            self.assertEqual(login.status_code, 200, login.text)
            self.assertEqual(login.json()["user"], original)

    def test_logout_requires_own_csrf_and_revokes_only_own_session(self):
        with self.client() as alice, self.client() as bob:
            first = self.register(alice, "alice@example.invalid")
            second = self.register(bob, "bob@example.invalid")
            old_cookies = dict(alice.cookies)
            for headers in ({}, {"X-CSRF-Token": second["csrfToken"]}):
                with self.subTest(headers_present=bool(headers)):
                    self.assertEqual(alice.post("/api/auth/logout", headers=headers).status_code, 403)
                    self.assertEqual(alice.get("/api/auth/me").json()["user"], first["user"])
            logout = alice.post("/api/auth/logout", headers={"X-CSRF-Token": first["csrfToken"]})
            self.assertEqual(logout.status_code, 200)
            alice.cookies.clear()
            alice.cookies.update(old_cookies)
            self.assertEqual(alice.get("/api/auth/me").status_code, 401)
            self.assertEqual(bob.get("/api/auth/me").json()["user"], second["user"])

    def test_invalid_registration_does_not_reserve_email_or_grant_role(self):
        with self.client() as client:
            payload = {"email": "qa@example.invalid", "name": "验收账号", "password": PASSWORD}
            for changes in ({"name": " "}, {"password": "short"}, {"role": "admin"}):
                with self.subTest(field=next(iter(changes))):
                    response = client.post("/api/auth/register", json={**payload, **changes})
                    self.assertEqual(response.status_code, 422)
                    self.assertNotIn((payload | changes)["password"], response.text)
                    self.assertEqual(client.get("/api/auth/me").status_code, 401)
            registered = self.register(client)
            self.assertEqual(registered["user"]["role"], "student")

    def test_account_survives_application_recreation(self):
        with self.client() as client:
            original = self.register(client)["user"]
        # A fresh application uses the same database, with no carried-over cookies.
        with self.client() as restarted:
            self.assertEqual(restarted.get("/api/auth/me").status_code, 401)
            login = restarted.post("/api/auth/login", json={
                "email": original["email"], "password": PASSWORD,
            })
            self.assertEqual(login.status_code, 200, login.text)
            self.assertEqual(login.json()["user"], original)

    def test_catalog_exposes_six_dimensions_and_only_backend_is_open(self):
        with self.client() as client:
            response = client.get("/api/catalog")
            self.assertEqual(response.status_code, 200)
            catalog = response.json()
            dimensions = {"programming", "algorithms", "database", "network", "os", "software"}
            self.assertEqual(len(catalog["dimensions"]), 6)
            self.assertEqual({item["id"] for item in catalog["dimensions"]}, dimensions)
            self.assertEqual({role["id"] for role in catalog["roles"]}, {"backend", "frontend", "algorithm", "qa"})
            self.assertEqual([role["id"] for role in catalog["roles"] if role["enabled"]], ["backend"])
            backend = next(role for role in catalog["roles"] if role["id"] == "backend")
            self.assertEqual(set(backend["topics"]), dimensions)
            self.assertTrue(all(backend["topics"].values()))
            self.assertNotIn('"questions"', response.text)
            self.assertNotIn('"correct"', response.text)


if __name__ == "__main__":
    unittest.main()
