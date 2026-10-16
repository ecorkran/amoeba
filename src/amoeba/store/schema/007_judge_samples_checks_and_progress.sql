-- Migration 007: judge samples, check results, and progress records.
--
-- Column names here must match the constants in sql_checks.py (the two new
-- tables) and sql_evidence.py (the verdicts addition), the single definition
-- sites. Nothing to backfill: existing verdicts get judge_invocation_id NULL,
-- which is what they are.
--
-- No CHECK constraints on vocabulary columns: the word lists are defined once,
-- in check_models.py, and the row mapping raises on an unknown value.

-- Samples of one judge invocation share this id (107, D1, D2).
ALTER TABLE verdicts ADD COLUMN judge_invocation_id TEXT;

-- Serves the invocation-consistency check and the verdicts filter.
CREATE INDEX idx_verdicts_judge_invocation
    ON verdicts (project_id, judge_invocation_id);

CREATE TABLE check_results (
    -- Arrival order: assigned when recorded, never reused.
    recorded_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    -- The caller's id and the retry key: first wins.
    id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    node_id TEXT NOT NULL REFERENCES nodes (id),
    -- Free data (for example "cf check"); never used as logic.
    name TEXT NOT NULL,
    outcome TEXT NOT NULL,
    -- NULL means the submitter did not report it.
    examined_count INTEGER,
    -- JSON text, opaque: what was checked. NULL when absent.
    examined TEXT,
    -- Opaque, for example the SHA of main a result should be compared against.
    baseline_ref TEXT,
    upstream TEXT NOT NULL,
    upstream_version TEXT NOT NULL,
    source TEXT NOT NULL,
    source_path TEXT,
    recorded_at TEXT NOT NULL
);

CREATE INDEX idx_check_results_node
    ON check_results (project_id, node_id, recorded_seq);

-- Write-only until a consumer defines its fields (D6, GitHub issue #5).
CREATE TABLE progress_records (
    recorded_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    node_id TEXT NOT NULL REFERENCES nodes (id),
    progress_kind TEXT NOT NULL,
    -- JSON text, opaque.
    content TEXT NOT NULL,
    upstream TEXT NOT NULL,
    upstream_version TEXT NOT NULL,
    source TEXT NOT NULL,
    source_path TEXT,
    recorded_at TEXT NOT NULL
);

CREATE INDEX idx_progress_records_node
    ON progress_records (project_id, node_id, recorded_seq);

-- examined_count is emitted as a JSON number or null. No standing: it is
-- computed on read, and a trigger cannot call that function. The kind literal
-- mirrors ChangeKind.CHECK_RECORDED in feed_models.py; the invariant test
-- (tests/store/test_feed_invariant.py) fails if it drifts. progress_records has
-- no trigger until it has a reader (D9, GitHub issue #5).
CREATE TRIGGER changes_check_recorded
AFTER INSERT ON check_results
BEGIN
    INSERT INTO changes (project_id, kind, node_id, subject_id, payload, recorded_at)
    VALUES (
        new.project_id,
        'check_recorded',
        new.node_id,
        new.id,
        json_object(
            'name', new.name,
            'outcome', new.outcome,
            'examined_count', new.examined_count
        ),
        new.recorded_at
    );
END;
