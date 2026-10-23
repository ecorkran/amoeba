-- Migration 009: the Runner's store contract (slice 121).
--
-- Column names here must match the constants in sql_inbox.py (the five new
-- messages columns) and sql_runner.py (the four new tables), which are the
-- single definition sites. Nothing to backfill: every new messages column is
-- nullable with no default, so existing rows read as "not set".

-- D2: how an intent's acknowledgment ended. NULL on a row acknowledged before
-- this migration (the outcome was not recorded then) and on any unacknowledged
-- or escalation row. The vocabulary lives in inbox_models.py.
ALTER TABLE messages ADD COLUMN acknowledgment_outcome TEXT;
ALTER TABLE messages ADD COLUMN acknowledgment_reason TEXT;

-- D4: a project-scoped escalation is an escalation row with a fault kind and
-- no node. closed_at / closed_by record the Runner closing it; node
-- escalations leave all three NULL (their closure is their block's resolution).
ALTER TABLE messages ADD COLUMN fault_kind TEXT;
ALTER TABLE messages ADD COLUMN closed_at TEXT;
ALTER TABLE messages ADD COLUMN closed_by TEXT;

-- At most one open project-scoped escalation per project and fault kind, in
-- the schema and not only in code. The WHERE clause is repeated literally by
-- the open-row selects, because SQLite uses a partial index only then.
CREATE UNIQUE INDEX idx_messages_open_project_escalation
    ON messages (project_id, fault_kind)
    WHERE channel = 'escalation' AND fault_kind IS NOT NULL AND closed_at IS NULL;

-- D6: write-once. A version is stored the first time a decision uses it.
CREATE TABLE routing_table_versions (
    version TEXT PRIMARY KEY,
    -- The table file's text, verbatim.
    content TEXT NOT NULL,
    first_used_at TEXT NOT NULL
);

-- D5: one row per routing decision. Append-only.
CREATE TABLE routing_decisions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    node_id TEXT NOT NULL REFERENCES nodes (id),
    -- The outcome entry this decision routes; NULL for a decision with none.
    journal_entry_id TEXT REFERENCES command_journal (id),
    -- JSON text, stored verbatim: the routing inputs as 126 reduced them.
    inputs TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    table_version TEXT NOT NULL REFERENCES routing_table_versions (version),
    amoeba_version TEXT NOT NULL,
    route TEXT NOT NULL,
    -- JSON text, stored verbatim.
    route_parameters TEXT NOT NULL,
    -- NULL when the decision did not count an attempt.
    attempt_step TEXT,
    -- The counter's value after this decision's increment; NULL when none.
    attempt_count INTEGER,
    decided_at TEXT NOT NULL
);

-- At most one decision per entry, so an outcome cannot be routed twice.
CREATE UNIQUE INDEX idx_routing_decisions_entry
    ON routing_decisions (journal_entry_id)
    WHERE journal_entry_id IS NOT NULL;

CREATE INDEX idx_routing_decisions_node
    ON routing_decisions (node_id, decided_at);

-- D7: incremented only by record_routing_decision.
CREATE TABLE attempt_counts (
    node_id TEXT NOT NULL REFERENCES nodes (id),
    step TEXT NOT NULL,
    count INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (node_id, step)
);

-- D8: one row per target. node_id NULL is the project target. drive and hold
-- are nullable booleans; NULL means "not set at this target".
CREATE TABLE desired_states (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    node_id TEXT REFERENCES nodes (id),
    drive INTEGER,
    drive_until_step TEXT,
    hold INTEGER,
    -- The intent that last set the row, kept as provenance.
    message_id TEXT NOT NULL REFERENCES messages (id),
    updated_at TEXT NOT NULL
);

-- SQLite treats NULLs as distinct, so one plain unique index cannot enforce
-- one row per target; two partial indexes do.
CREATE UNIQUE INDEX idx_desired_states_project_target
    ON desired_states (project_id)
    WHERE node_id IS NULL;

CREATE UNIQUE INDEX idx_desired_states_node_target
    ON desired_states (node_id)
    WHERE node_id IS NOT NULL;
