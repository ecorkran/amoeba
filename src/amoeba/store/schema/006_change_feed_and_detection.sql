-- Migration 006: the per-project change log, review watches, and the
-- detection ledger.
--
-- Column names here must match the constants in sql_feed.py, which is the
-- single definition site. Nothing to backfill: the feed of an upgraded store
-- starts empty.
--
-- No CHECK constraints on vocabulary columns: the word lists are defined once,
-- in feed_models.py, and the row mapping raises on an unknown value.

CREATE TABLE changes (
    -- The subscriber's cursor: assigned at commit, never reused.
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    -- Deliberately not a foreign key: a feed row must never block a future
    -- node deletion.
    node_id TEXT,
    subject_id TEXT NOT NULL,
    -- JSON text, built by the emitting trigger.
    payload TEXT NOT NULL,
    -- Copied from the emitting row's own timestamp column.
    recorded_at TEXT NOT NULL
);

-- Serves the follower: one project's changes after a cursor.
CREATE INDEX idx_changes_project_seq ON changes (project_id, seq);

CREATE TABLE review_watches (
    project_id TEXT NOT NULL,
    -- Absolute, stored as given; no symlink resolution.
    reviews_dir TEXT NOT NULL,
    -- Boolean as 0/1.
    active INTEGER NOT NULL,
    registered_at TEXT NOT NULL,
    -- NULL until the detection tenant takes the baseline.
    baselined_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_id, reviews_dir)
);

CREATE TABLE detected_reviews (
    -- Detection order.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    path TEXT NOT NULL,
    -- sha256 of the bytes examined.
    digest TEXT NOT NULL,
    outcome TEXT NOT NULL,
    node_id TEXT REFERENCES nodes (id),
    verdict_id TEXT REFERENCES verdicts (id),
    -- 105's parsed-content id; set for every file that parsed.
    record_id TEXT,
    detail TEXT,
    detected_at TEXT NOT NULL,
    UNIQUE (project_id, path, digest)
);

-- --------------------------------------------------------------------------
-- Emission triggers (D8). Each writes one changes row inside the transaction of
-- the write that fired it, so a change and its feed row commit together or not
-- at all. recorded_at is copied from the row's own timestamp column.
--
-- The kind literals below mirror ChangeKind in feed_models.py. A shipped
-- migration is frozen, so they are repeated here; the invariant test
-- (tests/store/test_feed_invariant.py) requires every kind to appear, which
-- fails if a literal drifts from the enum.
-- --------------------------------------------------------------------------

CREATE TRIGGER changes_node_created
AFTER INSERT ON nodes
BEGIN
    INSERT INTO changes (project_id, kind, node_id, subject_id, payload, recorded_at)
    VALUES (
        new.project_id,
        'node_created',
        new.id,
        new.id,
        json_object('kind', new.kind, 'parent_id', new.parent_id, 'status', new.status),
        new.created_at
    );
END;

CREATE TRIGGER changes_node_status_changed
AFTER UPDATE OF status ON nodes
WHEN old.status IS NOT new.status
BEGIN
    INSERT INTO changes (project_id, kind, node_id, subject_id, payload, recorded_at)
    VALUES (
        new.project_id,
        'node_status_changed',
        new.id,
        new.id,
        json_object('from', old.status, 'to', new.status),
        new.updated_at
    );
END;
