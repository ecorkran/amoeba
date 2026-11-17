-- Waking (slice 244, D1, D3). ADD COLUMN and CREATE TABLE only, so existing rows are
-- untouched and no rebuild is needed. Times are UTC ISO-8601 text.
--
-- members.wake_command is the command Amoeba starts, unattended, for a request to a
-- member with no live session. Null means no wake. It is set from the CLI's add.
--
-- wakes holds one row per wake and keeps it after the wake ends (the daily limit and
-- the "last wake" display are queries over these rows). The claim writes the row; the
-- wrapper writes command_pid and the end fields, or wake_after_send does for a start
-- failure. A row whose wrapper was killed stays unended, stops counting as running at
-- deadline_at, and is deleted by the sweep once past prune_after_days. directory is
-- null only for a start_failed row that Context Forge gave no path for. The outcome
-- CHECK list is pinned to WakeOutcome by tests/store/test_vocabulary_pinning.py.

ALTER TABLE members ADD COLUMN wake_command TEXT;

CREATE TABLE wakes (
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
                              'wrapper_failed')),
    exit_code   INTEGER,
    detail      TEXT,
    CHECK ((ended_at IS NULL) = (outcome IS NULL)),
    CHECK (exit_code IS NULL OR outcome = 'exited')
);

CREATE INDEX wakes_member_started ON wakes (member_id, started_at);
CREATE INDEX wakes_started ON wakes (started_at);
