-- Migration 005: review verdicts and the findings each one reported.
--
-- Column names here must match the constants in sql_evidence.py, which is the
-- single definition site. Nothing to backfill.
--
-- No CHECK constraints on vocabulary columns: the word lists are defined once,
-- in evidence_models.py, and the row mapping raises on an unknown value.

CREATE TABLE verdicts (
    -- Arrival order: assigned when recorded, never reused.
    recorded_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    -- The caller's id and the retry key: first wins.
    id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    node_id TEXT NOT NULL REFERENCES nodes (id),
    -- The journaled Squadron run command, when there was one.
    journal_entry_id TEXT REFERENCES command_journal (id),
    verdict TEXT NOT NULL,
    derivation TEXT NOT NULL,
    -- Booleans as 0/1; NULL means the input did not report it.
    fallback_used INTEGER,
    findings_parsed INTEGER,
    diff_truncated INTEGER,
    provider_failure INTEGER NOT NULL,
    review_type TEXT NOT NULL,
    model TEXT NOT NULL,
    requested_model TEXT,
    reviewed_sha TEXT,
    score REAL,
    -- JSON text; NULL when absent.
    criteria TEXT,
    tool_calls_made INTEGER,
    sq_run_id TEXT,
    upstream TEXT NOT NULL,
    upstream_version TEXT NOT NULL,
    source TEXT NOT NULL,
    source_path TEXT,
    recorded_at TEXT NOT NULL
);

-- Serves finding the previous round: one node's reviews of one type, by arrival.
CREATE INDEX idx_verdicts_previous_round
    ON verdicts (project_id, node_id, review_type, recorded_seq);

CREATE TABLE finding_observations (
    verdict_id TEXT NOT NULL REFERENCES verdicts (id),
    -- Position in the review's findings list, from 0.
    ordinal INTEGER NOT NULL,
    -- Squadron's F001-style number, kept as data only.
    position_id TEXT,
    severity TEXT NOT NULL,
    category TEXT,
    summary TEXT NOT NULL,
    location TEXT,
    normalized_location TEXT NOT NULL,
    normalized_summary TEXT NOT NULL,
    identity TEXT NOT NULL,
    identity_version INTEGER NOT NULL,
    PRIMARY KEY (verdict_id, ordinal)
);

CREATE INDEX idx_finding_observations_identity
    ON finding_observations (identity);
