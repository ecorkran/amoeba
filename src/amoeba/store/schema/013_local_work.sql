-- Local work through the hub (slice 262, D14). Times are UTC ISO-8601 text.
--
-- Justification for the rebuilds (the store contract allows one only with it):
-- questions.closed_reason and wakes.outcome each gain a value (machine_removed), and
-- SQLite cannot change a CHECK in place. So questions and wakes are rebuilt by
-- SQLite's documented procedure, as 003 and 008 rebuilt questions: create the new
-- table, copy the rows, drop the old table, rename. Both rebuilds carry every column,
-- index and trigger the table has at schema 12, 011's owner column and trigger
-- included. The runner turns foreign keys off around the transaction and runs
-- foreign_key_check before commit; answers references questions by (run_id,
-- paused_at) and every key is copied.
--
-- machine_id: the machine whose files the work needs (a question's run, a wake's
-- checkout). Null only after rm-machine, or in a row from before this migration until
-- the local opener gives it `local`. The triggers that refuse a new row with no
-- machine are created last: a trigger fires on INSERT ... SELECT, and every row the
-- copy writes has no machine yet.
--
-- questions.start_count and answers.resume_start_count: how many automatic starts
-- claim_work has handed out (D10). answers.resume_claim_id names the attempt that
-- holds the resume claim (D6). messages.wake_wanted_at: when send wanted a wake for
-- an open request (D8).

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
               OR closed_reason IN ('dismissed', 'run_moved_on', 'run_gone',
                                    'machine_removed')),
    closed_detail      TEXT,
    closed_at          TEXT,
    request_id         TEXT,
    start_attempted_at TEXT,
    owner_id           INTEGER REFERENCES owners (owner_id),
    machine_id         INTEGER REFERENCES machines (machine_id),
    start_count        INTEGER NOT NULL DEFAULT 0,
    CHECK (state <> 'waiting_on_request' OR request_id IS NOT NULL),
    PRIMARY KEY (run_id, paused_at)
);

INSERT INTO questions_new (
    run_id, paused_at, member_id, question, checkout, state, answering_run_id,
    waiting_reason, claimed_at, updated_at, slice_label, source_commit, passages,
    waiting_detail, evidence, closed_reason, closed_detail, closed_at, request_id,
    start_attempted_at, owner_id
)
SELECT
    run_id, paused_at, member_id, question, checkout, state, answering_run_id,
    waiting_reason, claimed_at, updated_at, slice_label, source_commit, passages,
    waiting_detail, evidence, closed_reason, closed_detail, closed_at, request_id,
    start_attempted_at, owner_id
FROM questions;

DROP TABLE questions;

ALTER TABLE questions_new RENAME TO questions;

CREATE TRIGGER questions_owner_required BEFORE INSERT ON questions
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'questions: owner_id is required; the store has no acting machine');
END;

CREATE INDEX questions_machine_state ON questions (machine_id, state);

CREATE TABLE wakes_new (
    wake_id     TEXT PRIMARY KEY,
    member_id   TEXT NOT NULL REFERENCES members (project_id),
    directory   TEXT,
    command     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    deadline_at TEXT NOT NULL,
    log_stem    TEXT,
    command_pid INTEGER,
    ended_at    TEXT,
    outcome     TEXT
        CHECK (outcome IS NULL
               OR outcome IN ('exited', 'timed_out', 'start_failed',
                              'wrapper_failed', 'machine_removed')),
    exit_code   INTEGER,
    detail      TEXT,
    owner_id    INTEGER REFERENCES owners (owner_id),
    machine_id  INTEGER REFERENCES machines (machine_id),
    CHECK ((ended_at IS NULL) = (outcome IS NULL)),
    CHECK (exit_code IS NULL OR outcome = 'exited')
);

INSERT INTO wakes_new (
    wake_id, member_id, directory, command, started_at, deadline_at, log_stem,
    command_pid, ended_at, outcome, exit_code, detail, owner_id
)
SELECT
    wake_id, member_id, directory, command, started_at, deadline_at, log_stem,
    command_pid, ended_at, outcome, exit_code, detail, owner_id
FROM wakes;

DROP TABLE wakes;

ALTER TABLE wakes_new RENAME TO wakes;

CREATE INDEX wakes_member_started ON wakes (member_id, started_at);

CREATE INDEX wakes_started ON wakes (started_at);

CREATE INDEX wakes_machine ON wakes (machine_id);

CREATE TRIGGER wakes_owner_required BEFORE INSERT ON wakes
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'wakes: owner_id is required; the store has no acting machine');
END;

ALTER TABLE answers ADD COLUMN resume_claim_id TEXT;

ALTER TABLE answers ADD COLUMN resume_start_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE messages ADD COLUMN wake_wanted_at TEXT;

CREATE TRIGGER questions_machine_required BEFORE INSERT ON questions
WHEN NEW.machine_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'questions: machine_id is required; the store has no acting machine');
END;

CREATE TRIGGER wakes_machine_required BEFORE INSERT ON wakes
WHEN NEW.machine_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'wakes: machine_id is required; the store has no acting machine');
END;
