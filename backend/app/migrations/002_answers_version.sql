ALTER TABLE attempts ADD COLUMN answers_version INTEGER NOT NULL DEFAULT 0 CHECK (answers_version >= 0);
