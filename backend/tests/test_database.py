"""T02 persistence contracts; no HTTP, authentication or scoring implementation."""
import json
import hashlib
from collections import Counter
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from pydantic import ValidationError

from app.models import QuestionInput
from app.catalog import BLUEPRINT, DIMENSION_IDS, ROLE_MAP
from app.config import Settings
from app.db import connect, dump, initialize, now_iso, transaction


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="skillproof-t02-")
        self.addCleanup(directory.cleanup)
        self.settings = Settings(
            database_path=Path(directory.name) / "nested" / "test.db",
            environment="development",
        )
        initialize(self.settings)
        self.con = connect(self.settings)
        self.addCleanup(self.con.close)

    def user(self, email=None):
        uid = str(uuid4())
        self.con.execute(
            "INSERT INTO users(id,email,name,role,password_hash,created_at) VALUES(?,?,?,'student',?,?)",
            (uid, email or uid + "@example.invalid", "T02 fixture", "test-only-placeholder-not-a-password-hash", now_iso()),
        )
        return uid

    def attempt(self, uid, *, submitted=False, role="backend"):
        aid = str(uuid4())
        question = json.loads(self.con.execute("SELECT content_json FROM questions ORDER BY id LIMIT 1").fetchone()[0])
        answers = {question["id"]: ["A"]}
        # Storage fixture only: this does not execute or validate a scoring algorithm.
        report = {"id": aid, "roleId": role, "dimensions": [
            {"id": key, "score": 0} for key in ROLE_MAP[role]["weights"]
        ]}
        self.con.execute(
            "INSERT INTO attempts(id,user_id,role_id,role_name,status,created_at,submitted_at,"
            "blueprint_version,model_version,questions_json,role_json,resources_json,answers_json,report_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, uid, role, ROLE_MAP[role]["name"], "submitted" if submitted else "in_progress",
             now_iso(), now_iso() if submitted else None, "2026.1", "2026.1", dump([question]),
             dump(ROLE_MAP[role]), "[]", dump(answers), dump(report) if submitted else None),
        )
        return aid

    def test_empty_directory_initialization(self):
        settings = Settings(database_path=self.settings.database_path.parent / "new" / "empty.db", environment="development")
        self.assertFalse(settings.database_path.parent.exists())
        initialize(settings)
        con = connect(settings)
        try:
            tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"users", "sessions", "questions", "question_versions", "attempts", "schema_migrations"} <= tables)
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        finally:
            con.close()

    def test_t03_seed_preserves_internal_fields_in_both_tables(self):
        seed = json.loads((self.settings.content_dir / "questions.json").read_text(encoding="utf-8"))
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM questions").fetchone()[0], len(seed))
        for question in seed:
            with self.subTest(question=question["id"]):
                current = self.con.execute("SELECT status,content_json FROM questions WHERE id=?", (question["id"],)).fetchone()
                version = self.con.execute("SELECT content_json FROM question_versions WHERE question_id=? AND version=?",
                                           (question["id"], question["version"])).fetchone()
                self.assertEqual(current["status"], question["status"])
                self.assertEqual(json.loads(current["content_json"]), question)
                self.assertEqual(json.loads(version["content_json"]), question)

    def test_seed_and_migrations_are_idempotent(self):
        def rows():
            return {table: [tuple(r) for r in self.con.execute(f"SELECT * FROM {table} ORDER BY 1,2")]
                    for table in ("questions", "question_versions", "schema_migrations")}
        before = rows()
        self.assertGreater(len(before["questions"]), 0)
        self.assertEqual(len(before["questions"]), len(before["question_versions"]))
        initialize(self.settings)
        initialize(self.settings)
        self.assertEqual(rows(), before)

    def test_answers_version_migration_preserves_existing_drafts_and_reports(self):
        uid = self.user()
        self.attempt(uid, submitted=True)
        self.attempt(uid)
        settings = Settings(database_path=self.settings.database_path.parent / "legacy.db", environment="development")
        with closing(sqlite3.connect(settings.database_path, isolation_level=None)) as legacy:
            legacy.executescript((BACKEND / "app/migrations/001_initial.sql").read_text(encoding="utf-8"))
            legacy.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            legacy.execute("INSERT INTO schema_migrations VALUES(1,?)", (now_iso(),))
            for table in ("users", "attempts"):
                columns = [row[1] for row in legacy.execute(f"PRAGMA table_info({table})")]
                names = ",".join(columns)
                rows = self.con.execute(f"SELECT {names} FROM {table}").fetchall()
                legacy.executemany(f"INSERT INTO {table}({names}) VALUES({','.join('?' for _ in columns)})", rows)
            before = legacy.execute("SELECT * FROM attempts ORDER BY id").fetchall()
        initialize(settings)
        initialize(settings)
        with closing(sqlite3.connect(settings.database_path)) as migrated:
            after = migrated.execute("SELECT * FROM attempts ORDER BY id").fetchall()
            self.assertEqual([row[:-1] for row in after], before)
            self.assertEqual([row[-1] for row in after], [0, 0])
            self.assertEqual(migrated.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall(), [(1,), (2,), (3,)])
            self.assertEqual(migrated.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_seed_does_not_overwrite_existing_question(self):
        row = self.con.execute("SELECT * FROM questions ORDER BY id LIMIT 1").fetchone()
        content = json.loads(row["content_json"])
        content["stem"] = "T02 test-only edited question"
        updated = dump(content)
        self.con.execute("UPDATE questions SET content_json=? WHERE id=?", (updated, row["id"]))
        with self.assertRaisesRegex(ValueError, 'conflict'):
            initialize(self.settings)
        self.assertEqual(self.con.execute("SELECT content_json FROM questions WHERE id=?", (row["id"],)).fetchone()[0], updated)

    def test_data_survives_new_process_and_reinitialization(self):
        uid = self.user()
        self.con.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", ("test-token-hash", uid, "test-csrf", now_iso(), 9999999999.0))
        self.attempt(uid)
        self.attempt(uid, submitted=True)
        tables = ("users", "sessions", "attempts")
        before = {t: [tuple(r) for r in self.con.execute(f"SELECT * FROM {t} ORDER BY 1")] for t in tables}
        self.con.close()
        code = (
            "from pathlib import Path; from app.config import Settings; from app.db import initialize; "
            "import sys; initialize(Settings(database_path=Path(sys.argv[1]), environment='development'))"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.settings.database_path)], cwd=BACKEND, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        con = connect(self.settings)
        try:
            after = {t: [tuple(r) for r in con.execute(f"SELECT * FROM {t} ORDER BY 1")] for t in tables}
            self.assertEqual(after, before)
        finally:
            con.close()

    def test_duplicate_email_rejected(self):
        self.user("duplicate@example.invalid")
        with self.assertRaises(sqlite3.IntegrityError):
            self.user("duplicate@example.invalid")

    def test_foreign_keys_reject_missing_owner(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.attempt("missing-user")
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", ("missing", "missing-user", "csrf", now_iso(), 1.0))

    def test_multiple_submissions_and_new_active_attempt_allowed(self):
        uid = self.user()
        ids = {self.attempt(uid, submitted=True), self.attempt(uid, submitted=True), self.attempt(uid)}
        self.assertEqual(len(ids), 3)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts WHERE user_id=?", (uid,)).fetchone()[0], 3)

    def test_one_active_attempt_per_user_matches_current_contract(self):
        uid = self.user()
        self.attempt(uid)
        for role in ("backend", "frontend"):
            with self.subTest(role=role), self.assertRaises(sqlite3.IntegrityError):
                self.attempt(uid, role=role)
        self.attempt(self.user())  # A different user may have an active attempt.

    def test_status_report_timestamp_consistency(self):
        aid = self.attempt(self.user())
        for update in ("status='submitted'", "report_json='{}'", "submitted_at='2026-11-01T00:00:00Z'", "status='unknown'"):
            with self.subTest(update=update), self.assertRaises(sqlite3.IntegrityError):
                self.con.execute(f"UPDATE attempts SET {update} WHERE id=?", (aid,))
        self.con.execute("UPDATE attempts SET status='submitted', report_json='{}', submitted_at=? WHERE id=?", (now_iso(), aid))
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("UPDATE attempts SET report_json=NULL WHERE id=?", (aid,))

    def test_question_edit_does_not_change_stored_snapshots(self):
        aid = self.attempt(self.user(), submitted=True)
        query = "SELECT questions_json,role_json,answers_json,report_json FROM attempts WHERE id=?"
        before = tuple(self.con.execute(query, (aid,)).fetchone())
        self.con.execute("UPDATE questions SET content_json='{}',version=version+1")
        self.assertEqual(tuple(self.con.execute(query, (aid,)).fetchone()), before)

    def test_owner_scoped_query_and_cascade_preserve_other_user(self):
        first, second = self.user(), self.user()
        aid, other = self.attempt(first), self.attempt(second)
        self.assertIsNone(self.con.execute("SELECT id FROM attempts WHERE id=? AND user_id=?", (aid, second)).fetchone())
        self.con.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", ("cascade", first, "csrf", now_iso(), 1.0))
        self.con.execute("DELETE FROM users WHERE id=?", (first,))
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM sessions WHERE user_id=?", (first,)).fetchone()[0], 0)
        self.assertIsNone(self.con.execute("SELECT id FROM attempts WHERE id=?", (aid,)).fetchone())
        self.assertIsNotNone(self.con.execute("SELECT id FROM attempts WHERE id=?", (other,)).fetchone())

    def test_transaction_rolls_back_partial_write(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.con):
                self.user("rollback@example.invalid")
                self.user("rollback@example.invalid")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM users WHERE email=?", ("rollback@example.invalid",)).fetchone()[0], 0)


class QuestionValidationTests(unittest.TestCase):
    def setUp(self):
        self.question = json.loads((BACKEND / "app/content/questions.json").read_text(encoding="utf-8"))[0]

    def test_draft_accepts_empty_sources_and_retains_topic_id(self):
        self.question.update(status="draft", sources=[])
        parsed = QuestionInput.model_validate(self.question)
        self.assertEqual(parsed.model_dump()["topicId"], self.question["topicId"])
        self.assertEqual(parsed.sources, [])
        self.assertEqual(parsed.status, "draft")

    def test_published_question_requires_sources(self):
        self.question["status"] = "published"
        self.question["sources"] = []
        with self.assertRaises(ValidationError):
            QuestionInput.model_validate(self.question)
        self.question["sources"] = [{"title": "Test fixture source", "url": "https://example.com/reference"}]
        self.assertEqual(QuestionInput.model_validate(self.question).status, "published")

    def test_default_bank_manifest_and_published_quota(self):
        content = BACKEND / "app/content"
        manifest = json.loads((content / "manifest.json").read_text(encoding="utf-8"))
        questions = json.loads((content / "questions.json").read_text(encoding="utf-8"))
        self.assertEqual(len(questions), manifest["questionCount"])
        self.assertEqual(len({q["id"] for q in questions}), len(questions))
        for filename, digest in manifest["files"].items():
            self.assertEqual(hashlib.sha256((content / filename).read_bytes()).hexdigest(), digest)
        published = [QuestionInput.model_validate(q) for q in questions if q["status"] == "published"]
        strata = Counter((q.dimension, q.difficulty) for q in published)
        for dimension in DIMENSION_IDS:
            for difficulty, total in BLUEPRINT["difficultyCounts"].items():
                self.assertGreaterEqual(strata[(dimension, difficulty)], total // len(DIMENSION_IDS))

    def test_unknown_fields_and_blank_topic_id_are_rejected(self):
        for extra in ({"unexpected": True}, {"topicId": " "}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                QuestionInput.model_validate({**self.question, **extra})


if __name__ == "__main__":
    unittest.main()
