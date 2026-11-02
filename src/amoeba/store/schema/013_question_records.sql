-- Migration 013: question records (slice 141, D1-D3, D7).
--
-- One row per agent question. Column, index and table names here must match the
-- constants in sql_questions.py, the single definition site. The feed kind
-- literals in the triggers mirror ChangeKind in feed_models.py; the invariant
-- test (tests/store/test_feed_invariant.py) fails if one drifts.
-- state, answered_by and decline_reason hold the vocabularies in
-- question_models.py. blocked_state_id is null only for a question declined
-- 'node_already_blocked'; an acknowledgment moves it to the re-block (D2).
-- Nothing to backfill: questions already in the journal are not recorded.

CREATE TABLE question_records (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    node_id TEXT NOT NULL REFERENCES nodes (id),
    -- The sq_run journal entry whose run ended on the question (D1).
    source_entry_id TEXT NOT NULL UNIQUE REFERENCES command_journal (id),
    run_id TEXT NOT NULL,
    step TEXT,
    question TEXT,
    -- Boolean as 0/1.
    truncated INTEGER NOT NULL,
    blocked_state_id TEXT REFERENCES blocked_states (id),
    state TEXT NOT NULL,
    answered_by TEXT,
    answer TEXT,
    decline_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- A block carries at most one question.
CREATE UNIQUE INDEX idx_question_records_blocked_state
    ON question_records (blocked_state_id) WHERE blocked_state_id IS NOT NULL;

-- Serves pending_questions and the questions listing.
CREATE INDEX idx_question_records_project_state
    ON question_records (project_id, state, created_at);

CREATE INDEX idx_question_records_node ON question_records (node_id);

-- Emission triggers (D7). Payloads carry no question or answer text.
CREATE TRIGGER changes_question_recorded
AFTER INSERT ON question_records
BEGIN
    INSERT INTO changes (project_id, kind, node_id, subject_id, payload, recorded_at)
    VALUES (
        new.project_id,
        'question_recorded',
        new.node_id,
        new.id,
        json_object('state', new.state, 'decline_reason', new.decline_reason),
        new.created_at
    );
END;

CREATE TRIGGER changes_question_state_changed
AFTER UPDATE OF state ON question_records
WHEN old.state IS NOT new.state
BEGIN
    INSERT INTO changes (project_id, kind, node_id, subject_id, payload, recorded_at)
    VALUES (
        new.project_id,
        'question_state_changed',
        new.node_id,
        new.id,
        json_object(
            'from', old.state,
            'to', new.state,
            'answered_by', new.answered_by,
            'decline_reason', new.decline_reason
        ),
        new.updated_at
    );
END;
