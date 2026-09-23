-- Migration 004: the inbox submission record and the message queue.
--
-- Column names here must match the constants in sql_inbox.py, which is the
-- single definition site.
--
-- Both tables carry an INTEGER PRIMARY KEY AUTOINCREMENT. That key is the
-- receiver-assigned order (D4): assigned at apply, never reused after a delete,
-- and authoritative where the submitter's own submitted_at is not.

CREATE TABLE inbox_submissions (
    applied_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    -- The submitter's id and the idempotency key (D2): first wins.
    id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    submitted_by TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    -- JSON text, stored verbatim.
    payload TEXT NOT NULL,
    outcome TEXT NOT NULL,
    -- NULL when applied; the rejection reason otherwise.
    reason TEXT,
    applied_at TEXT NOT NULL
);

CREATE TABLE messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    node_id TEXT REFERENCES nodes (id),
    -- Set for escalations.
    blocked_state_id TEXT REFERENCES blocked_states (id),
    -- Set when recovery raised the escalation.
    journal_entry_id TEXT REFERENCES command_journal (id),
    -- Set for intents, as provenance. Deliberately not a foreign key: the
    -- intent row is written before its submission record inside the same
    -- apply transaction, and foreign keys are checked immediately.
    submission_id TEXT,
    -- JSON text, opaque to the store. NULL when absent.
    payload TEXT,
    created_at TEXT NOT NULL,
    acknowledged_at TEXT,
    acknowledged_by TEXT
);

-- Serves the replay primitive: one channel of one project, after a cursor.
CREATE INDEX idx_messages_project_channel_seq
    ON messages (project_id, channel, seq);

-- Serves pending_intents. Partial, because consumed intents accumulate without
-- bound and the Runner never looks at them.
CREATE INDEX idx_messages_unacknowledged_intents
    ON messages (project_id, seq)
    WHERE channel = 'intent' AND acknowledged_at IS NULL;

-- Backfill (D3): every OPEN human block gets its escalation row, so from
-- version 4 onward a human-blocked node without one cannot exist. Resolved
-- historical blocks are not backfilled. Ordered by block time so seq follows
-- the order the blocks happened in. Ids match new_id(): 32 lowercase hex.
INSERT INTO messages (
    id,
    project_id,
    channel,
    node_id,
    blocked_state_id,
    created_at
)
SELECT
    lower(hex(randomblob(16))),
    nodes.project_id,
    'escalation',
    blocked_states.node_id,
    blocked_states.id,
    blocked_states.created_at
FROM blocked_states
JOIN nodes ON nodes.id = blocked_states.node_id
WHERE blocked_states.kind = 'human'
  AND blocked_states.resolved_at IS NULL
ORDER BY blocked_states.created_at, blocked_states.id;
