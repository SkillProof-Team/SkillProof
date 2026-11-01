CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student','admin')),
    target_role TEXT,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE TABLE questions (
    id TEXT PRIMARY KEY,
    dimension TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('published','draft','archived')),
    version INTEGER NOT NULL CHECK(version >= 1),
    content_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE question_versions (
    question_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(question_id, version)
);
CREATE TABLE attempts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL,
    role_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('in_progress','submitted')),
    created_at TEXT NOT NULL,
    submitted_at TEXT,
    blueprint_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    questions_json TEXT NOT NULL,
    role_json TEXT NOT NULL,
    resources_json TEXT NOT NULL,
    answers_json TEXT NOT NULL DEFAULT '{}',
    report_json TEXT,
    reused_question_count INTEGER NOT NULL DEFAULT 0,
    CHECK((status = 'in_progress' AND report_json IS NULL AND submitted_at IS NULL) OR (status = 'submitted' AND report_json IS NOT NULL AND submitted_at IS NOT NULL))
);
CREATE INDEX idx_attempts_user ON attempts(user_id, created_at DESC);
CREATE UNIQUE INDEX one_active_attempt_per_user ON attempts(user_id) WHERE status = 'in_progress';
CREATE TABLE rate_limits (
    key_hash TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    expires_at REAL NOT NULL
);
