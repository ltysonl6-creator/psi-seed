"""SQLite schema and connection initialization."""

SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    current_version INTEGER NOT NULL CHECK (current_version >= 1),
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_revisions (
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    revision_event_id TEXT,
    PRIMARY KEY (entity_id, version),
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    causation_ref TEXT,
    correlation_ref TEXT,
    related_entity_refs_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    integrity_hash TEXT,
    correction_of_ref TEXT,
    supersedes_ref TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_sequence ON events(sequence);

CREATE TABLE IF NOT EXISTS outcomes (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_relationship_source
    ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_relationship_target
    ON relationships(target_id);

CREATE TABLE IF NOT EXISTS failures (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    failure_class TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_failures_entity
    ON failures(entity_id);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

def initialize_connection(conn):
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(SCHEMA_SQL)
    # v0.10 migration: make status part of the authoritative revision state.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(entity_revisions)")}
    if "status" not in columns:
        conn.execute("ALTER TABLE entity_revisions ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        conn.execute(
            "UPDATE entity_revisions SET status = (SELECT status FROM entities WHERE entities.id = entity_revisions.entity_id)"
        )
    conn.commit()
