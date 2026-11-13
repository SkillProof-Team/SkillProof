"""Validate and synchronize the repository-owned question bank without deleting data."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .models import QuestionInput
from .catalog import project_catalog


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def version_key(value: str) -> tuple:
    """Compare x.y.z releases and SemVer prereleases (e.g. 0.1.2-draft)."""
    match = re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?', value)
    if not match:
        raise ValueError('bankVersion must be x.y.z with an optional prerelease suffix')
    major, minor, patch, suffix = match.groups()
    parts = suffix.split('.') if suffix is not None else []
    if any(part.isdigit() and len(part) > 1 and part.startswith('0') for part in parts):
        raise ValueError('bankVersion numeric prerelease identifiers cannot have leading zeroes')
    return (int(major), int(minor), int(patch), suffix is None,
            tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts))


@dataclass(frozen=True)
class Bank:
    id: str
    version: str
    content_hash: str
    questions: tuple[dict, ...]
    catalog: dict


def load_bank(directory: Path) -> Bank:
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if not isinstance(manifest, dict):
        raise ValueError('Question bank manifest must be an object')
    if manifest.get('schemaVersion') != '1.0' or manifest.get('roleId') != 'backend':
        raise ValueError('Unsupported question bank schemaVersion or roleId')
    if (manifest.get('questionFile') != 'questions.json'
            or manifest.get('abilityTreeFile') != 'ability-tree.json'):
        raise ValueError('Question bank manifest must reference the standard content files')
    bank_id, bank_version = manifest.get('bankId'), manifest.get('bankVersion')
    if not isinstance(bank_id, str) or not bank_id.strip() or not isinstance(bank_version, str):
        raise ValueError('Question bank manifest requires bankId and bankVersion')
    version_key(bank_version)
    hashes = manifest.get('files')
    if not isinstance(hashes, dict) or set(hashes) != {'questions.json', 'ability-tree.json'}:
        raise ValueError('Question bank manifest requires both file SHA-256 values')
    # Parse the exact bytes whose digests were checked, not a second read of the files.
    files = {}
    for name, expected in hashes.items():
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f'Question bank SHA-256 mismatch: {name}; update manifest.json')
        files[name] = json.loads(raw)
    raw_questions = files['questions.json']
    if (not isinstance(raw_questions, list) or type(manifest.get('questionCount')) is not int
            or len(raw_questions) != manifest['questionCount'] or not raw_questions):
        raise ValueError('Question bank questionCount must match a nonempty questions list')
    questions = tuple(QuestionInput.model_validate(q).model_dump() for q in raw_questions)
    ids = [q['id'] for q in questions]
    if None in ids or len(set(ids)) != len(ids):
        raise ValueError('Seed questions must have unique, non-null IDs')
    if any(type(raw.get('version')) is not int or raw['version'] < 1 for raw in raw_questions):
        raise ValueError('Seed questions require an explicit positive integer version')
    try:
        catalog = project_catalog(files['ability-tree.json'])
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Invalid ability tree structure') from exc
    fingerprint = canonical({'questions': sorted(questions, key=lambda q: q['id']),
                             'abilityTree': files['ability-tree.json']})
    return Bank(bank_id, bank_version, hashlib.sha256(fingerprint.encode('utf-8')).hexdigest(), questions, catalog)


def stored_question(raw: str) -> dict:
    return QuestionInput.model_validate_json(raw).model_dump()


def record_version(con: sqlite3.Connection, question: dict, applied_at: str) -> None:
    existing = con.execute('SELECT content_json FROM question_versions WHERE question_id=? AND version=?',
                           (question['id'], question['version'])).fetchone()
    if existing:
        if stored_question(existing['content_json']) != question:
            raise ValueError(f"Question {question['id']} version history conflict; resolve before syncing")
    else:
        con.execute('INSERT INTO question_versions(question_id,version,content_json,created_at) VALUES(?,?,?,?)',
                    (question['id'], question['version'], canonical(question), applied_at))


def sync_bank(con: sqlite3.Connection, bank: Bank, applied_at: str) -> None:
    """Caller must hold a write transaction, including the state/version checks."""
    state = con.execute('SELECT * FROM question_bank_state WHERE id=1').fetchone()
    ids = {q['id'] for q in bank.questions}
    if state:
        if state['bank_id'] != bank.id:
            raise ValueError('Question bank bankId conflict; a different bank cannot replace this one')
        if version_key(bank.version) < version_key(state['bank_version']):
            raise ValueError('Question bank bankVersion downgrade is not allowed')
        if state['bank_version'] == bank.version and state['content_hash'] != bank.content_hash:
            raise ValueError('Question bank content changed without increasing bankVersion')
        if set(json.loads(state['question_ids_json'])) - ids:
            raise ValueError('Do not remove question IDs; increment version and mark them archived')
    for question in bank.questions:
        row = con.execute('SELECT * FROM questions WHERE id=?', (question['id'],)).fetchone()
        if row:
            current = stored_question(row['content_json'])
            if (current['id'], current['dimension'], current['status'], current['version']) != (
                    row['id'], row['dimension'], row['status'], row['version']):
                raise ValueError(f"Question {question['id']} stored metadata conflict")
            if row['version'] > question['version']:
                raise ValueError(f"Question {question['id']} version downgrade is not allowed")
            if row['version'] == question['version']:
                if current != question:
                    raise ValueError(f"Question {question['id']} same version content conflict; increase version")
                record_version(con, question, applied_at)
                continue
            previous = con.execute('SELECT content_json FROM question_versions WHERE question_id=? AND version=?',
                                   (row['id'], row['version'])).fetchone()
            if not previous or stored_question(previous['content_json']) != current:
                raise ValueError(f"Question {question['id']} local edit/history conflict; resolve before syncing")
            con.execute('UPDATE questions SET dimension=?,status=?,version=?,content_json=?,updated_at=? WHERE id=?',
                        (question['dimension'], question['status'], question['version'], canonical(question),
                         applied_at, question['id']))
        else:
            con.execute('INSERT INTO questions(id,dimension,status,version,content_json,updated_at) VALUES(?,?,?,?,?,?)',
                        (question['id'], question['dimension'], question['status'], question['version'],
                         canonical(question), applied_at))
        record_version(con, question, applied_at)
    if not state or state['bank_version'] != bank.version:
        con.execute('INSERT INTO question_bank_state(id,bank_id,bank_version,content_hash,question_ids_json,applied_at) '
                    'VALUES(1,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET bank_id=excluded.bank_id,'
                    'bank_version=excluded.bank_version,content_hash=excluded.content_hash,'
                    'question_ids_json=excluded.question_ids_json,applied_at=excluded.applied_at',
                    (bank.id, bank.version, bank.content_hash, canonical(sorted(ids)), applied_at))
