"""Real HTTP save ordering against temporary SQLite; gates only delay transport."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest

import httpx
import uvicorn

from app.config import Settings
from app.db import connect, initialize
from app.main import create_app

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support.question_bank import assessment_questions, write_bank


class AnswerSaveOrderTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.settings = Settings(database_path=Path(directory) / "ordering.sqlite3",
                                 content_dir=write_bank(Path(directory) / "content", assessment_questions()),
                                 environment="development", cookie_secure=False, origin=None,
                                 allowed_hosts=("127.0.0.1",))
        initialize(self.settings)
        self.con = self.enterContext(closing(connect(self.settings)))
        app = create_app(self.settings)
        self.blocked = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.delayed_status = None

        async def gated_app(scope, receive, send):
            mode = dict(scope.get("headers", [])).get(b"x-test-delay")
            messages = []
            if mode == b"before":
                while True:
                    message = await receive()
                    messages.append(message)
                    if not message.get("more_body", False):
                        break
                self.blocked.set()
                if not await asyncio.to_thread(self.release.wait, 5):
                    raise RuntimeError("Save request gate timed out")
            response_done = asyncio.Event()

            async def buffered_receive():
                if messages:
                    return messages.pop(0)
                await response_done.wait()
                return {"type": "http.disconnect"}

            async def delayed_send(message):
                if mode and message["type"] == "http.response.start":
                    self.delayed_status = message["status"]
                if mode == b"after" and message["type"] == "http.response.start":
                    self.blocked.set()
                    if not await asyncio.to_thread(self.release.wait, 5):
                        raise RuntimeError("Save response gate timed out")
                await send(message)
                if message["type"] == "http.response.body" and not message.get("more_body", False):
                    response_done.set()

            await app(scope, buffered_receive if mode == b"before" else receive, delayed_send)
            if mode:
                self.finished.set()

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(gated_app, log_level="error", lifespan="on"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)

        def stop():
            self.release.set()
            server.should_exit = True
            thread.join(5)
            listener.close()
            self.assertFalse(thread.is_alive(), "HTTP server did not stop")

        self.addCleanup(stop)
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(server.started)
        self.base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        self.client = self.enterContext(httpx.Client(base_url=self.base_url, timeout=3, trust_env=False))
        self.assertEqual(self.client.get("/api/health").json(), {"Status": "ok"})
        self.headers = self.register(self.client, "owner")
        created = self.client.post("/api/attempts", json={"roleId": "backend"}, headers=self.headers)
        self.assertEqual(created.status_code, 200, created.text)
        self.attempt = created.json()
        self.url = f"/api/attempts/{self.attempt['id']}"
        self.qid = next(q["id"] for q in self.attempt["questions"] if q["type"] == "single")

    def register(self, client, name):
        response = client.post("/api/auth/register", json={
            "email": f"{name}@example.com", "name": name, "password": "ordering-acceptance-password",
        })
        self.assertEqual(response.status_code, 201, response.text)
        return {"X-CSRF-Token": response.json()["csrfToken"]}

    def save(self, answers, version, *, client=None, headers=None, timeout=3):
        return (client or self.client).put(self.url + "/answers", json={
            "answers": answers, "expectedVersion": version,
        }, headers=self.headers if headers is None else headers, timeout=timeout)

    def persisted(self, answers, version):
        latest = self.client.get(self.url).json()
        self.assertEqual(latest["answers"], answers)
        self.assertEqual(latest["answersVersion"], version)
        row = self.con.execute("SELECT answers_json,answers_version FROM attempts WHERE id=?", (self.attempt["id"],)).fetchone()
        self.assertEqual(json.loads(row["answers_json"]), answers)
        self.assertEqual(row["answers_version"], version)
        return latest

    def test_normal_save_rapid_changes_clear_and_refresh(self):
        choices = {self.qid: ["A"]}
        self.assertEqual(self.save(choices, 0).status_code, 200)
        multiple = next(q["id"] for q in self.attempt["questions"] if q["type"] == "multiple")
        for version, selected in enumerate((["B"], ["C"], [], ["D"], ["B"]), 1):
            self.assertEqual(self.save({self.qid: selected, multiple: ["A", "B"]}, version).status_code, 200)
        self.persisted({self.qid: ["B"], multiple: ["A", "B"]}, 6)
        self.assertEqual(self.save({self.qid: []}, 6).status_code, 200)
        self.persisted({multiple: ["A", "B"]}, 7)
        with httpx.Client(base_url=self.base_url, cookies=self.client.cookies, trust_env=False) as refreshed:
            self.assertEqual(refreshed.get(self.url).json()["answers"], {multiple: ["A", "B"]})

    def test_timed_out_A_arrives_after_B_and_is_rejected(self):
        with httpx.Client(base_url=self.base_url, cookies=self.client.cookies, trust_env=False) as old:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(self.save, {self.qid: ["A"]}, 0, client=old,
                                      headers={**self.headers, "X-Test-Delay": "before"}, timeout=0.2)
                self.assertTrue(self.blocked.wait(2))
                with self.assertRaises(httpx.ReadTimeout):
                    pending.result()
            self.assertEqual(self.save({self.qid: ["B"]}, 0).status_code, 200)
            self.release.set()
            self.assertTrue(self.finished.wait(2))
            self.assertEqual(self.delayed_status, 409)
        # A retries with its original version also receive a real 409.
        self.assertEqual(self.save({self.qid: ["A"]}, 0).status_code, 409)
        self.persisted({self.qid: ["B"]}, 1)

    def test_A_completes_first_B_conflicts_then_syncs_and_retries(self):
        self.assertEqual(self.save({self.qid: ["A"]}, 0).status_code, 200)
        response = self.save({self.qid: ["B"]}, 0)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "answers_version_conflict")
        latest = self.persisted({self.qid: ["A"]}, 1)
        self.assertEqual(self.save({self.qid: ["B"]}, latest["answersVersion"]).status_code, 200)
        self.persisted({self.qid: ["B"]}, 2)

    def test_lost_success_response_is_confirmed_by_get(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.save, {self.qid: ["A"]}, 0,
                                  headers={**self.headers, "X-Test-Delay": "after"}, timeout=0.2)
            self.assertTrue(self.blocked.wait(2))
            with self.assertRaises(httpx.ReadTimeout):
                pending.result()
        self.persisted({self.qid: ["A"]}, 1)
        self.release.set()
        self.assertEqual(self.save({self.qid: ["B"]}, 1).status_code, 200)
        self.persisted({self.qid: ["B"]}, 2)

    def test_two_clients_same_version_only_one_write_succeeds(self):
        barrier = threading.Barrier(2)
        with httpx.Client(base_url=self.base_url, cookies=self.client.cookies, trust_env=False) as other:
            def write(client, option):
                barrier.wait(2)
                return self.save({self.qid: [option]}, 0, client=client)

            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(write, self.client, "A")
                second = pool.submit(write, other, "B")
                responses = [first.result(), second.result()]
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        winner = next(r.json() for r in responses if r.status_code == 200)
        self.persisted(winner["answers"], 1)

    def test_status_errors_and_save_before_submit(self):
        for body in ({"answers": {}}, {"answers": {}, "expectedVersion": -1},
                     {"answers": {}, "expectedVersion": True}, {"answers": {}, "expectedVersion": "0"}):
            self.assertEqual(self.client.put(self.url + "/answers", json=body, headers=self.headers).status_code, 422)
        self.assertEqual(self.save({self.qid: ["Z"]}, 0).status_code, 422)
        self.assertEqual(self.save({}, 0, headers={}).status_code, 403)
        self.assertEqual(self.client.post(self.url + "/submit", headers=self.headers).status_code, 422)
        self.persisted({}, 0)
        with httpx.Client(base_url=self.base_url, trust_env=False) as other:
            self.assertEqual(self.save({}, 0, client=other).status_code, 401)
            headers = self.register(other, "other")
            self.assertEqual(self.save({}, 0, client=other, headers=headers).status_code, 404)
        self.assertEqual(self.client.put("/api/attempts/missing/answers", json={"answers": {}, "expectedVersion": 0}, headers=self.headers).status_code, 404)
        answers = {q["id"]: [q["options"][0]["id"]] for q in self.attempt["questions"]}
        self.assertEqual(self.save(answers, 0).status_code, 200)
        submitted = self.client.post(self.url + "/submit", headers=self.headers)
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(self.save({}, 1).status_code, 409)
        self.assertEqual(self.client.post(self.url + "/submit", headers=self.headers).json(), submitted.json())
        self.assertEqual(self.client.get(f"/api/reports/{self.attempt['id']}").json(), submitted.json())
        self.persisted(answers, 1)
        self.con.execute("UPDATE sessions SET expires_at=0")
        self.assertEqual(self.save({}, 1).status_code, 401)
