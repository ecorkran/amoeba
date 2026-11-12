-- Question lifecycle (slice 228, D3). Times are UTC ISO-8601 text, as before.
--
-- This is the one exception to the "later migrations only ADD COLUMN" rule (222 D3).
-- A new question state means widening questions.state's CHECK list, and SQLite
-- cannot change a CHECK in place. The alternative, a closed_at column beside an
-- unchanged state, would split one state across two columns that every reader must
-- combine. So questions is rebuilt once, by SQLite's documented procedure: create
-- the new table, copy the rows, drop the old table, rename. The runner turns foreign
-- keys off around the transaction and runs foreign_key_check before commit.
-- Migrations after this one go back to ADD COLUMN, and a new exception needs the
-- same justification in its slice design. Neither 001 nor 002 defines an index, so
-- none is recreated. Every CHECK list below is pinned to its enum by
-- tests/store/test_vocabulary_pinning.py.

CREATE TABLE questions_new (
    run_id           TEXT NOT NULL,
    paused_at        TEXT NOT NULL,
    member_id        TEXT NOT NULL REFERENCES members (project_id),
    question         TEXT NOT NULL,
    checkout         TEXT NOT NULL,
    state            TEXT NOT NULL
        CHECK (state IN ('claimed', 'answered', 'waiting_on_pm', 'closed')),
    answering_run_id TEXT,
    waiting_reason   TEXT,
    claimed_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    slice_label      TEXT,
    source_commit    TEXT,
    passages         TEXT,
    waiting_detail   TEXT,
    evidence         TEXT,
    closed_reason    TEXT
        CHECK (closed_reason IS NULL
               OR closed_reason IN ('dismissed', 'run_moved_on', 'run_gone')),
    closed_detail    TEXT,
    closed_at        TEXT,
    PRIMARY KEY (run_id, paused_at)
);

INSERT INTO questions_new (
    run_id, paused_at, member_id, question, checkout, state, answering_run_id,
    waiting_reason, claimed_at, updated_at, slice_label, source_commit, passages,
    waiting_detail, evidence
)
SELECT
    run_id, paused_at, member_id, question, checkout, state, answering_run_id,
    waiting_reason, claimed_at, updated_at, slice_label, source_commit, passages,
    waiting_detail, evidence
FROM questions;

DROP TABLE questions;

ALTER TABLE questions_new RENAME TO questions;

-- When a PM answer was retracted, and why (D6). The answer stays delivered.
ALTER TABLE answers ADD COLUMN retracted_at TEXT;
ALTER TABLE answers ADD COLUMN retract_reason TEXT;
-- Set just before each resume spawn, so a sweep never closes one in flight (D4).
ALTER TABLE answers ADD COLUMN resume_started_at TEXT;

-- When set_up removed the member (D8). The row stays: its questions are the record.
ALTER TABLE members ADD COLUMN removed_at TEXT;
