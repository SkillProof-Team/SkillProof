"""Account and catalog acceptance through the real API and an isolated database."""

import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect
from app.main import create_app
from app.security import PASSWORD_HASHER, password_matches

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

    def client(self, **settings_overrides):
        settings = replace(self.settings, **settings_overrides)
        return TestClient(create_app(settings), headers={"Origin": "http://testserver"})

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

    def test_registration_replaces_and_revokes_the_previous_session(self):
        with self.client() as client, self.client() as replay:
            previous = self.register(client)["user"]
            replay.cookies.update(dict(client.cookies))
            before = replay.get("/api/auth/me")
            self.assertEqual(before.status_code, 200, before.text)
            self.assertEqual(before.json()["user"], previous)

            current = self.register(client, "next@example.invalid")["user"]
            self.assertNotEqual(current["id"], previous["id"])
            me = client.get("/api/auth/me")
            self.assertEqual(me.status_code, 200, me.text)
            self.assertEqual(me.json()["user"], current)
            rejected = replay.get("/api/auth/me")
            self.assertEqual(rejected.status_code, 401, rejected.text)

    def test_login_rejects_account_changes_after_password_verification(self):
        for change in ("password", "delete"):
            with self.subTest(change=change), self.client() as client:
                user = self.register(client, f"{change}@example.invalid")["user"]
                client.cookies.clear()

                def verify_then_change_account(hashed, password, change=change, user_id=user["id"]):
                    matches = password_matches(hashed, password)
                    self.assertTrue(matches)
                    with closing(connect(self.settings)) as con:
                        if change == "delete":
                            con.execute("DELETE FROM users WHERE id=?", (user_id,))
                        else:
                            new_hash = PASSWORD_HASHER.hash("replacement passphrase")
                            con.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user_id))
                    return matches

                with patch("app.api_auth.password_matches", side_effect=verify_then_change_account):
                    response = client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD})
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(response.json(), {"detail": "账户状态已变化，请重新登录"})
                self.assertNotIn("set-cookie", response.headers)

    def test_login_rate_limit_returns_retry_after(self):
        with self.client(login_limit=1) as client:
            payload = {"email": "missing@example.invalid", "password": PASSWORD}
            self.assertEqual(client.post("/api/auth/login", json=payload).status_code, 401)

            response = client.post("/api/auth/login", json=payload)
            self.assertEqual(response.status_code, 429, response.text)
            self.assertIn("retry-after", response.headers)
            self.assertIn(int(response.headers["retry-after"]), range(1, self.settings.rate_window_seconds + 1))

    def test_registration_rate_limit_returns_retry_after(self):
        with self.client(register_limit=1) as client:
            self.register(client)
            response = client.post("/api/auth/register", json={
                "email": "next@example.invalid", "name": "验收账号", "password": PASSWORD,
            })
            self.assertEqual(response.status_code, 429, response.text)
            self.assertIn("retry-after", response.headers)
            self.assertIn(int(response.headers["retry-after"]), range(1, self.settings.rate_window_seconds + 1))

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

    def test_registration_rejects_invalid_email_and_password(self):
        cases = (
            ("consecutive dots", "email", "qa..test@example.invalid"),
            ("long local part", "email", "a" * 65 + "@example.invalid"),
            ("whitespace only", "password", " " * 15),
            ("over 512 UTF-8 bytes", "password", "🔒" * 129),
        )
        with self.client() as client:
            payload = {"email": "qa@example.invalid", "name": "验收账号", "password": PASSWORD}
            for case, field, value in cases:
                with self.subTest(case=case):
                    response = client.post("/api/auth/register", json={**payload, field: value})
                    self.assertEqual(response.status_code, 422, response.text)
                    errors = response.json()["detail"]["errors"]
                    self.assertEqual([error["field"] for error in errors], [f"body.{field}"])

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

    def test_catalog_exposes_six_dimensions_and_all_roles_are_open(self):
        with self.client() as client:
            response = client.get("/api/catalog")
            self.assertEqual(response.status_code, 200)
            catalog = response.json()
            dimensions = {"programming", "algorithms", "database", "network", "os", "software"}
            self.assertEqual(len(catalog["dimensions"]), 6)
            self.assertEqual({item["id"] for item in catalog["dimensions"]}, dimensions)
            self.assertEqual({role["id"] for role in catalog["roles"]}, {"backend", "frontend", "algorithm", "qa"})
            self.assertTrue(all(role["enabled"] for role in catalog["roles"]))
            backend = next(role for role in catalog["roles"] if role["id"] == "backend")
            self.assertEqual(set(backend["topics"]), dimensions)
            self.assertTrue(all(backend["topics"].values()))
            self.assertNotIn('"questions"', response.text)
            self.assertNotIn('"correct"', response.text)


if __name__ == "__main__":
    unittest.main()
