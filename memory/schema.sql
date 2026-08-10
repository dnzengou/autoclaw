-- memory/schema.sql — three-tier persistent memory. Stdlib SQLite only.

CREATE TABLE IF NOT EXISTS personal_memory (
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    owner       TEXT NOT NULL DEFAULT 'default',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (owner, key)
);
CREATE INDEX IF NOT EXISTS idx_personal_owner ON personal_memory(owner);

CREATE TABLE IF NOT EXISTS session_memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL CHECK(role IN ('user','assistant','system','summary')),
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    tokens      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_session ON session_memory(session_id, id);

CREATE TABLE IF NOT EXISTS org_memory (
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    author      TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (key, version)
);
CREATE INDEX IF NOT EXISTS idx_org_key ON org_memory(key);
