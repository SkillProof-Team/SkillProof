CREATE TABLE population_config(role_id TEXT PRIMARY KEY, preset_json TEXT NOT NULL, weight REAL NOT NULL CHECK(weight>=0));
CREATE TABLE population_vectors(role_id TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, attempt_id TEXT NOT NULL, vector_json TEXT NOT NULL, PRIMARY KEY(role_id,user_id));
CREATE TABLE population_summary(role_id TEXT PRIMARY KEY, sample_count INTEGER NOT NULL, vector_json TEXT NOT NULL, updated_at TEXT NOT NULL);
