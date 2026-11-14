CREATE TABLE question_bank_state (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    bank_id TEXT NOT NULL,
    bank_version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    question_ids_json TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
