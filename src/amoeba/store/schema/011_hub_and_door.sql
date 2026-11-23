-- The hub and the door (slice 260, D12). Adds only: it deletes and rebuilds nothing.
-- Times are UTC ISO-8601 text.
--
-- owners: the one owner of every record. The migration inserts it, named pm; both
-- ways (a laptop's store and a hub's) run this same migration.
-- machines: one row per machine that may call the hub, or the local machine. The
-- hub keeps only the SHA-256 of a machine's token. No machine is made here: the
-- local opener makes `local`, and `amoeba hub invite` makes the rest.
-- call_results: the kept result of a writing call, so a repeated call applies once.
-- closed_mark: at most one row; set when the store is set aside for a hub.
-- owner_id on the twelve record tables, with a trigger that refuses a null so an
-- insert that forgets the owner fails loudly. SQLite cannot add a NOT NULL column
-- without a default, and a default owner would be a silent fallback.

CREATE TABLE owners (
    owner_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

INSERT INTO owners (name, created_at) VALUES ('pm', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));

CREATE TABLE machines (
    machine_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    owner_id       INTEGER NOT NULL REFERENCES owners (owner_id),
    token_hash     TEXT UNIQUE,
    created_at     TEXT NOT NULL,
    last_called_at TEXT,
    client_version TEXT
);

CREATE TABLE call_results (
    machine_id   INTEGER NOT NULL REFERENCES machines (machine_id),
    call_id      TEXT NOT NULL,
    operation    TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    reply        TEXT NOT NULL,
    recorded_at  TEXT NOT NULL,
    PRIMARY KEY (machine_id, call_id)
);

CREATE INDEX call_results_recorded_at ON call_results (recorded_at);

CREATE TABLE closed_mark (
    mark_key    INTEGER PRIMARY KEY CHECK (mark_key = 1),
    hub_address TEXT NOT NULL,
    closed_at   TEXT NOT NULL
);

ALTER TABLE programs ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE programs SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER programs_owner_required BEFORE INSERT ON programs
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'programs: owner_id is required; the store has no acting machine');
END;

ALTER TABLE members ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE members SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER members_owner_required BEFORE INSERT ON members
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'members: owner_id is required; the store has no acting machine');
END;

ALTER TABLE dependency_pairs ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE dependency_pairs SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER dependency_pairs_owner_required BEFORE INSERT ON dependency_pairs
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'dependency_pairs: owner_id is required; the store has no acting machine');
END;

ALTER TABLE releases ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE releases SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER releases_owner_required BEFORE INSERT ON releases
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'releases: owner_id is required; the store has no acting machine');
END;

ALTER TABLE questions ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE questions SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER questions_owner_required BEFORE INSERT ON questions
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'questions: owner_id is required; the store has no acting machine');
END;

ALTER TABLE answers ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE answers SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER answers_owner_required BEFORE INSERT ON answers
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'answers: owner_id is required; the store has no acting machine');
END;

ALTER TABLE standing_answers ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE standing_answers SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER standing_answers_owner_required BEFORE INSERT ON standing_answers
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'standing_answers: owner_id is required; the store has no acting machine');
END;

ALTER TABLE messages ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE messages SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER messages_owner_required BEFORE INSERT ON messages
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'messages: owner_id is required; the store has no acting machine');
END;

ALTER TABLE deliveries ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE deliveries SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER deliveries_owner_required BEFORE INSERT ON deliveries
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'deliveries: owner_id is required; the store has no acting machine');
END;

ALTER TABLE message_rejections ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE message_rejections SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER message_rejections_owner_required BEFORE INSERT ON message_rejections
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'message_rejections: owner_id is required; the store has no acting machine');
END;

ALTER TABLE sessions ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE sessions SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER sessions_owner_required BEFORE INSERT ON sessions
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'sessions: owner_id is required; the store has no acting machine');
END;

ALTER TABLE wakes ADD COLUMN owner_id INTEGER REFERENCES owners (owner_id);

UPDATE wakes SET owner_id = (SELECT owner_id FROM owners);

CREATE TRIGGER wakes_owner_required BEFORE INSERT ON wakes
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'wakes: owner_id is required; the store has no acting machine');
END;

-- A session's machine, so `amoeba hub rm-machine` can remove the machine's sessions.
-- Rows written before this migration keep a null machine; the heartbeat prune
-- removes them.
ALTER TABLE sessions ADD COLUMN machine_id INTEGER REFERENCES machines (machine_id);

CREATE TRIGGER sessions_machine_required BEFORE INSERT ON sessions
WHEN NEW.machine_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'sessions: machine_id is required; the store has no acting machine');
END;
