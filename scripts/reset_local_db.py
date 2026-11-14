"""Explicitly reset a stopped development database, retaining a SQLite backup."""
import argparse
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from dotenv import load_dotenv
from app.config import Settings
from app.db import initialize


def backup_database(source, target, timeout=15):
    deadline = time.monotonic() + timeout

    def progress(status, remaining, total):
        if status != sqlite3.SQLITE_DONE and time.monotonic() >= deadline:
            raise TimeoutError('SQLite backup timed out; stop other database users and retry')

    source.backup(target, pages=256, progress=progress, sleep=0.05)


def reset_database(settings: Settings) -> Path | None:
    if settings.environment != 'development':
        raise ValueError('Database reset is only allowed in the development environment')
    database = settings.database_path.resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    # Build and validate the replacement first. A bad bank never changes the old database.
    with tempfile.TemporaryDirectory(prefix='skillproof-reset-', dir=database.parent) as folder:
        fresh = Path(folder) / 'fresh.db'
        initialize(replace(settings, database_path=fresh))
        with closing(sqlite3.connect(fresh)) as source:
            with closing(sqlite3.connect(database, timeout=15)) as target:
                # SQLite backup includes committed WAL content; do not copy/unlink DB sidecars.
                if target.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():
                    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                    backup_path = database.with_name(f'{database.stem}.backup-{stamp}-{uuid4().hex[:8]}{database.suffix}')
                    with closing(sqlite3.connect(backup_path)) as backup:
                        backup_database(target, backup)
                backup_database(source, target)
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Stop the backend first. Reset local test data and seed the current bank; keep a backup.')
    parser.add_argument('--yes', action='store_true', help='Confirm clearing all local accounts, sessions and assessments')
    parser.add_argument('--db-path', type=Path, help='Override SKILLPROOF_DB_PATH')
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env', help='Configuration file; existing process variables take precedence')
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    settings = Settings()
    if args.db_path is not None:
        settings = replace(settings, database_path=args.db_path)
    if not args.yes:
        parser.error(f'Reset requires --yes. Target: {settings.database_path.resolve()}')
    try:
        backup = reset_database(settings)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f'Reset failed: {error}\n')
    print(json.dumps({'database': str(settings.database_path.resolve()),
                      'backup': str(backup) if backup else None}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
