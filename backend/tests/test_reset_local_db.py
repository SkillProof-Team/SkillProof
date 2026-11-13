"""Exercise the explicit reset CLI using only disposable development databases."""
from contextlib import closing
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys
import tempfile
import unittest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.config import Settings
from app.db import connect, initialize, now_iso
sys.path.insert(0, str(BACKEND.parent / 'scripts'))
from reset_local_db import backup_database, reset_database


class ResetLocalDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.database = self.root / 'local.db'
        self.settings = Settings(database_path=self.database, environment='development')
        initialize(self.settings)
        with closing(connect(self.settings)) as con:
            con.execute("INSERT INTO users(id,email,name,role,password_hash,created_at) VALUES('local','local@example.invalid','Local','student','test-only',?)", (now_iso(),))
            # Reset must also work when ordinary startup would reject a manual edit.
            con.execute("UPDATE questions SET content_json='{}'")
        self.env = {k:v for k,v in os.environ.items() if not k.startswith('SKILLPROOF_')}
        self.env.update(SKILLPROOF_ENV='development', PYTHONUTF8='1')

    def cli(self, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', str(BACKEND.parent/'scripts/reset_local_db.py'),
                               '--env-file', str(self.root/'absent.env'), *args],
                              env=self.env, capture_output=True, text=True, encoding='utf-8', timeout=20)

    def test_reset_requires_confirmation_without_changing_database(self):
        before = self.database.read_bytes()
        result = self.cli('--db-path', str(self.database))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('--yes', result.stderr)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(self.root.glob('*.backup-*')), [])

    def test_reset_keeps_backup_and_reinitializes_current_bank(self):
        result = self.cli('--db-path', str(self.database), '--yes')
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        backup = Path(payload['backup'])
        self.assertTrue(backup.is_file())
        with closing(sqlite3.connect(backup)) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
            self.assertEqual(con.execute('SELECT content_json FROM questions LIMIT 1').fetchone()[0], '{}')
        with closing(connect(self.settings)) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM users').fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM questions WHERE status='published'").fetchone()[0], 42)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0], 42)
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        initialize(self.settings)

    def test_reset_rejects_production(self):
        before = self.database.read_bytes()
        self.env['SKILLPROOF_ENV'] = 'production'
        result = self.cli('--db-path', str(self.database), '--yes')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('only allowed in the development', result.stderr)
        self.assertEqual(self.database.read_bytes(), before)

    def test_reset_uses_environment_file_database_path(self):
        env_file = self.root/'config.env'
        env_file.write_text(f'SKILLPROOF_DB_PATH={self.database.as_posix()}\n', encoding='utf-8')
        result = self.cli('--env-file', str(env_file), '--yes')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(json.loads(result.stdout)['database']), self.database.resolve())

    def test_backup_stops_retrying_when_destination_is_locked(self):
        target_path = self.root / 'locked.db'
        with closing(sqlite3.connect(self.database)) as source, closing(sqlite3.connect(target_path, timeout=.01)) as target:
            with closing(sqlite3.connect(target_path)) as lock:
                lock.execute('CREATE TABLE marker(id INTEGER)')
                lock.execute('BEGIN EXCLUSIVE')
                try:
                    with self.assertRaisesRegex(TimeoutError, 'timed out'):
                        backup_database(source, target, timeout=.1)
                finally:
                    lock.rollback()
            self.assertEqual(target.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [('marker',)])

    def test_invalid_seed_leaves_old_database_untouched(self):
        content = self.root / 'invalid-content'
        shutil.copytree(self.settings.content_dir, content)
        with (content/'questions.json').open('a', encoding='utf-8') as stream:
            stream.write(' ')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            reset_database(replace(self.settings, content_dir=content))
        with closing(connect(self.settings)) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
            self.assertEqual(con.execute('SELECT content_json FROM questions LIMIT 1').fetchone()[0], '{}')
        self.assertEqual(list(self.root.glob('*.backup-*')), [])

    def test_backup_includes_committed_wal_data(self):
        with closing(connect(self.settings)) as con:
            con.execute('PRAGMA wal_autocheckpoint=0')
            con.execute("UPDATE users SET name='Committed WAL edit' WHERE id='local'")
            self.assertTrue(Path(str(self.database)+'-wal').exists())
            backup = reset_database(self.settings)
            with closing(sqlite3.connect(backup)) as saved:
                self.assertEqual(saved.execute('SELECT name FROM users').fetchone()[0], 'Committed WAL edit')
                self.assertEqual(saved.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(con.execute('SELECT COUNT(*) FROM users').fetchone()[0], 0)
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')


if __name__ == '__main__':
    unittest.main()
