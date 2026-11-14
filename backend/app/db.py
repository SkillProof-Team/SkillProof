"""SQLite persistence with versioned migrations and transactional seed imports."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .config import Settings
from .question_bank import load_bank, sync_bank


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def connect(settings: Settings) -> sqlite3.Connection:
    # FastAPI can resume a synchronous dependency on a different worker thread;
    # each request still owns exactly one connection and uses it sequentially.
    con = sqlite3.connect(str(settings.database_path), timeout=15, isolation_level=None, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=15000")
    return con


@contextmanager
def transaction(con: sqlite3.Connection):
    """Serialize writers, including read-modify-write decisions, across processes."""
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def load_content(directory: Path, filename: str, key: str | None = None):
    with (directory / filename).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if key and isinstance(value, dict):
        return value.get(key, value.get("items", []))
    return value


def initialize(settings: Settings) -> dict:
    settings.validate()
    bank = load_bank(settings.content_dir)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    con = connect(settings)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
            version = int(path.name.split("_", 1)[0])
            # The lock covers the version check, so simultaneous worker startup is safe.
            with transaction(con):
                if con.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,)).fetchone():
                    continue
                # Each migration intentionally contains ordinary, semicolon-delimited DDL.
                for statement in path.read_text(encoding="utf-8").split(";"):
                    if statement.strip():
                        con.execute(statement)
                con.execute("INSERT INTO schema_migrations(version,applied_at) VALUES(?,?)", (version, now_iso()))
        # All bank checks, current rows, immutable history and release state commit together.
        with transaction(con):
            sync_bank(con, bank, now_iso())
    finally:
        con.close()
    return bank.catalog
