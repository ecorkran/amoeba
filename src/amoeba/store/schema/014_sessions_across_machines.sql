-- Sessions across machines (slice 263, D5, D6, D13). Adds only: it deletes and
-- rebuilds nothing. Times are UTC ISO-8601 text, and every time in `sessions` is the
-- store's own clock (the hub's, through the door).
--
-- sessions.client_version, sessions.door_version: the versions of the program that
-- serves the session, so `list` can show which sessions are behind the hub. Null only
-- in a row from before this migration, which is not live (LIVE_SESSION needs a door
-- version) and goes at the next prune. The trigger refuses a new row without them.
-- machines.door_version: the door version of the machine's last call that was not a
-- session's tick or exit call.
-- machine_runs: the `runs` document each machine last reported through `status` or
-- `list`, one row per machine, so other machines can show its runs.

ALTER TABLE sessions ADD COLUMN client_version TEXT;

ALTER TABLE sessions ADD COLUMN door_version INTEGER;

CREATE TRIGGER sessions_versions_required BEFORE INSERT ON sessions
WHEN NEW.client_version IS NULL OR NEW.door_version IS NULL
BEGIN
    SELECT RAISE(ABORT, 'sessions: client_version and door_version are required; the session cannot say what program serves it');
END;

ALTER TABLE machines ADD COLUMN door_version INTEGER;

CREATE TABLE machine_runs (
    machine_id  INTEGER PRIMARY KEY REFERENCES machines (machine_id),
    owner_id    INTEGER REFERENCES owners (owner_id),
    reported_at TEXT NOT NULL,
    document    TEXT NOT NULL
);

CREATE TRIGGER machine_runs_owner_required BEFORE INSERT ON machine_runs
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'machine_runs: owner_id is required; the store has no acting machine');
END;
