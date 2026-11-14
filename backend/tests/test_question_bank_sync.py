"""Versioned repository bank upgrades on disposable SQLite databases."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient
from app.config import Settings
from app.db import connect, dump, initialize, now_iso
from app.main import create_app


class QuestionBankSyncTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.content = root / 'content'
        shutil.copytree(BACKEND / 'app/content', self.content)
        self.settings = Settings(database_path=root / 'bank.db', content_dir=self.content,
                                 environment='development', origin=None, cookie_secure=False,
                                 allowed_hosts=('testserver',))
        self.questions = json.loads((self.content / 'questions.json').read_text(encoding='utf-8'))
        self.manifest = json.loads((self.content / 'manifest.json').read_text(encoding='utf-8'))

    def write_bank(self, version=None):
        if version:
            self.manifest['bankVersion'] = version
        (self.content / 'questions.json').write_text(json.dumps(self.questions, ensure_ascii=False), encoding='utf-8')
        self.manifest['questionCount'] = len(self.questions)
        for name in self.manifest['files']:
            self.manifest['files'][name] = hashlib.sha256((self.content / name).read_bytes()).hexdigest()
        (self.content / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def rows(self):
        with closing(connect(self.settings)) as con:
            return {table: [tuple(r) for r in con.execute(f'SELECT * FROM {table} ORDER BY 1,2')]
                    for table in ('questions', 'question_versions', 'question_bank_state', 'users', 'sessions', 'attempts')}

    def seed_legacy(self):
        """Build the real pre-sync schema, not a database initialized by the new code."""
        with closing(sqlite3.connect(self.settings.database_path, isolation_level=None)) as con:
            con.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
            for version in (1, 2):
                path = next((BACKEND / 'app/migrations').glob(f'{version:03d}_*.sql'))
                con.executescript(path.read_text(encoding='utf-8'))
                con.execute('INSERT INTO schema_migrations VALUES(?,?)', (version, now_iso()))
            for q in self.questions:
                old = dict(q, status='draft', sources=[], version=q['version']-1)
                con.execute('INSERT INTO questions VALUES(?,?,?,?,?,?)', (old['id'], old['dimension'], old['status'], old['version'], dump(old), now_iso()))
                con.execute('INSERT INTO question_versions VALUES(?,?,?,?)', (old['id'], old['version'], dump(old), now_iso()))

    def test_legacy_draft_bank_upgrades_and_creates_assessment(self):
        self.seed_legacy()
        with TestClient(create_app(self.settings)) as client:
            credentials = {'email':'upgrade@example.invalid', 'password':'upgrade-test-password-2026'}
            self.assertEqual(client.post('/api/auth/register', json=dict(credentials, name='upgrade')).status_code, 201)
            auth = client.post('/api/auth/login', json=credentials).json()
            response = client.post('/api/attempts', json={'roleId':'backend'}, headers={'X-CSRF-Token':auth['csrfToken']})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(len(response.json()['questions']), 18)
        with closing(connect(self.settings)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM questions WHERE status='published'").fetchone()[0], 42)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0], 84)

    def test_add_update_archive_and_restart_are_idempotent(self):
        initialize(self.settings)
        original = self.questions[0].copy()
        self.questions[0].update(stem='Updated question text for version sync', version=original['version']+1)
        self.questions[1].update(status='archived', version=self.questions[1]['version']+1)
        self.questions.append(dict(original, id='sync-new-question', version=1))
        self.write_bank('0.1.4')
        initialize(self.settings)
        state = self.rows()
        current = {r[0]:json.loads(r[4]) for r in state['questions']}
        self.assertEqual(current[original['id']], self.questions[0])
        self.assertEqual(current[self.questions[1]['id']]['status'], 'archived')
        self.assertIn('sync-new-question', current)
        self.assertEqual(len(state['question_versions']), 45)
        initialize(self.settings)
        self.assertEqual(self.rows(), state)

    def test_changed_question_requires_new_bank_version(self):
        initialize(self.settings)
        before = self.rows()
        self.questions[0].update(stem='Changed question without bank release', version=self.questions[0]['version']+1)
        self.write_bank()
        with self.assertRaisesRegex(ValueError, 'bankVersion'):
            initialize(self.settings)
        self.assertEqual(self.rows(), before)

    def test_same_question_version_conflict_rolls_back_other_updates(self):
        initialize(self.settings)
        before = self.rows()
        self.questions[0].update(stem='A valid higher version updated first', version=self.questions[0]['version']+1)
        self.questions[-1]['stem'] = 'A changed question without version increment'
        self.write_bank('0.1.4')
        with self.assertRaisesRegex(ValueError, 'version'):
            initialize(self.settings)
        self.assertEqual(self.rows(), before)

    def test_question_downgrade_is_rejected(self):
        initialize(self.settings)
        before = self.rows()
        self.questions[0]['version'] -= 1
        self.write_bank('0.1.4')
        with self.assertRaisesRegex(ValueError, 'version'):
            initialize(self.settings)
        self.assertEqual(self.rows(), before)

    def test_bank_downgrade_is_rejected(self):
        initialize(self.settings)
        before = self.rows()
        self.write_bank('0.1.2-draft')
        with self.assertRaisesRegex(ValueError, 'bankVersion'):
            initialize(self.settings)
        self.assertEqual(self.rows(), before)

    def test_removing_question_requires_explicit_archive(self):
        initialize(self.settings)
        before = self.rows()
        self.questions.pop()
        self.write_bank('0.1.4')
        with self.assertRaisesRegex(ValueError, 'archiv'):
            initialize(self.settings)
        self.assertEqual(self.rows(), before)

    def test_bad_hash_is_rejected_before_bank_changes(self):
        initialize(self.settings)
        before = self.rows()
        with (self.content / 'questions.json').open('a', encoding='utf-8') as stream:
            stream.write(' ')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            initialize(self.settings)
        self.assertEqual(self.rows(), before)

    def test_duplicate_ids_and_missing_versions_are_rejected(self):
        for invalid in ('duplicate', 'missing-version'):
            with self.subTest(invalid=invalid):
                original = [dict(q) for q in self.questions]
                if invalid == 'duplicate':
                    self.questions.append(self.questions[0].copy())
                else:
                    self.questions[0].pop('version')
                self.write_bank()
                with self.assertRaises(ValueError):
                    initialize(self.settings)
                self.questions = original

    def test_invalid_tree_does_not_advance_bank_state(self):
        initialize(self.settings)
        before = self.rows()
        tree_path = self.content / 'ability-tree.json'
        tree = json.loads(tree_path.read_text(encoding='utf-8'))
        tree['dimensions'].pop()
        tree_path.write_text(json.dumps(tree), encoding='utf-8')
        self.write_bank('0.1.4')
        with self.assertRaises(ValueError):
            initialize(self.settings)
        self.assertEqual(self.rows(), before)

    def test_local_edits_are_not_silently_overwritten(self):
        initialize(self.settings)
        with closing(connect(self.settings)) as con:
            edited = dict(self.questions[0], stem='Local change that needs conflict resolution')
            con.execute('UPDATE questions SET content_json=? WHERE id=?', (dump(edited), edited['id']))
        before = self.rows()
        self.questions[0].update(stem='Repository update of the same edited question', version=edited['version']+1)
        self.write_bank('0.1.4')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            initialize(self.settings)
        self.assertEqual(self.rows(), before)

    def test_concurrent_initialization_only_records_one_version(self):
        initialize(self.settings)
        self.questions[0]['version'] += 1
        self.questions[0]['stem'] = 'Concurrent update should be recorded once'
        self.write_bank('0.1.4')
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: initialize(self.settings), range(3)))
        self.assertEqual(len(self.rows()['question_versions']), 43)

    def test_sync_preserves_users_sessions_and_attempt_snapshots(self):
        with TestClient(create_app(self.settings)) as client:
            auth = client.post('/api/auth/register', json={'email':'snapshot@example.invalid', 'name':'snapshot', 'password':'snapshot-test-password-2026'}).json()
            headers = {'X-CSRF-Token':auth['csrfToken']}
            first = client.post('/api/attempts', json={'roleId':'backend'}, headers=headers).json()
            answers = {q['id']:q['correct'] for q in self.questions if q['id'] in {q['id'] for q in first['questions']}}
            self.assertEqual(client.put(f"/api/attempts/{first['id']}/answers", json={'answers':answers, 'expectedVersion':0}, headers=headers).status_code, 200)
            report = client.post(f"/api/attempts/{first['id']}/submit", headers=headers).json()
            active = client.post('/api/attempts', json={'roleId':'backend'}, headers=headers).json()
            before = self.rows()
            for q in self.questions:
                q.update(stem='Repository replacement wording for future assessments', version=q['version']+1)
            self.write_bank('0.1.4')
            initialize(self.settings)
            after = self.rows()
            for table in ('users', 'sessions', 'attempts'):
                self.assertEqual(after[table], before[table])
            self.assertEqual(client.get(f"/api/attempts/{active['id']}").json(), active)
            self.assertEqual(client.get(f"/api/reports/{first['id']}").json(), report)
            self.assertEqual(report['score'], 100)


if __name__ == '__main__':
    unittest.main()
