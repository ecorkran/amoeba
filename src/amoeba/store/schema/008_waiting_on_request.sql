-- A question held on a request (slice 242, D2). Times are UTC ISO-8601 text.
--
-- Justification for the rebuild (the store contract allows one only with it): a new
-- question state means widening questions.state's CHECK list, and SQLite cannot
-- change a CHECK in place. A held flag beside an unchanged state would split one
-- state across two columns that every reader must combine. So questions is rebuilt
-- by SQLite's documented procedure, as 003 did: create the new table, copy the rows,
-- drop the old table, rename. The runner turns foreign keys off around the
-- transaction and runs foreign_key_check before commit. No migration defines an
-- index on questions, so none is recreated. answers references questions by
-- (run_id, paused_at); every key is copied, so those references hold.
--
-- request_id names the request a held question waits on. It has no foreign key to
-- messages: 240's sweep prunes terminal requests by age, and a foreign key would
-- make that prune fail while a question still names the request. start_attempted_at
-- is when start_ended_held last started handle_pause for the row; it is its own
-- column because close_question uses updated_at as its compare-and-set guard.

CREATE TABLE questions_new (
    run_id             TEXT NOT NULL,
    paused_at          TEXT NOT NULL,
    member_id          TEXT NOT NULL REFERENCES members (project_id),
    question           TEXT NOT NULL,
    checkout           TEXT NOT NULL,
    state              TEXT NOT NULL
        CHECK (state IN ('claimed', 'answered', 'waiting_on_pm', 'closed',
                         'waiting_on_request')),
    answering_run_id   TEXT,
    waiting_reason     TEXT,
    claimed_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    slice_label        TEXT,
    source_commit      TEXT,
    passages           TEXT,
    waiting_detail     TEXT,
    evidence           TEXT,
    closed_reason      TEXT
        CHECK (closed_reason IS NULL
               OR closed_reason IN ('dismissed', 'run_moved_on', 'run_gone')),
    closed_detail      TEXT,
    closed_at          TEXT,
    request_id         TEXT,
    start_attempted_at TEXT,
    CHECK (state <> 'waiting_on_request' OR request_id IS NOT NULL),
    PRIMARY KEY (run_id, paused_at)
);

INSERT INTO questions_new (
    run_id, paused_at, member_id, question, checkout, state, answering_run_id,
    waiting_reason, claimed_at, updated_at, slice_label, source_commit, passages,
    waiting_detail, evidence, closed_reason, closed_detail, closed_at
)
SELECT
    run_id, paused_at, member_id, question, checkout, state, answering_run_id,
    waiting_reason, claimed_at, updated_at, slice_label, source_commit, passages,
    waiting_detail, evidence, closed_reason, closed_detail, closed_at
FROM questions;

DROP TABLE questions;

ALTER TABLE questions_new RENAME TO questions;
