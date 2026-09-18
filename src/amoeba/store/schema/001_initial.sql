-- Migration 001: initial schema.
--
-- Creates the schema version stamp, the project-keyed lifecycle node tree, and
-- blocked states with their explicit resolution slot. Column names here must
-- match the constants in sql.py, which is the single definition site.

CREATE TABLE schema_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    parent_id TEXT REFERENCES nodes (id),
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    title TEXT NOT NULL,
    cf_project TEXT,
    cf_phase TEXT,
    cf_slice TEXT,
    cf_artifact_path TEXT,
    sq_run_id TEXT,
    sq_review_artifact_path TEXT,
    sq_reviewed_sha TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Covers both Runner queries: runnable-for-project and blocked-for-project.
-- No other index is created; additional indexes wait for a measured need.
CREATE INDEX idx_nodes_project_status ON nodes (project_id, status);

CREATE TABLE blocked_states (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes (id),
    kind TEXT NOT NULL,
    context TEXT NOT NULL,
    -- The resolution slot. Nullable by design: an unfilled slot is the
    -- checkpoint. Filling it is what flips the node back to runnable.
    resolved_by TEXT,
    resolution_detail TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- At most one unresolved blocked state per node, so node status and
-- blocked-state cannot disagree about which block is current.
CREATE UNIQUE INDEX idx_blocked_states_open_node
    ON blocked_states (node_id)
    WHERE resolved_at IS NULL;
