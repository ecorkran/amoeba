-- Members by name (slice 261, D1, D2). Adds only: it deletes and rebuilds nothing.
-- Times are UTC ISO-8601 text.
--
-- members.name: the member's name, compared without regard to case, null only for a
-- row from before this migration; the naming step (operations.naming) fills it. The
-- trigger refuses a new member with no name, so only old rows can be unnamed.
-- members.origin: the reduced remote (host[:port]/path) or null; two active members
-- never share one. Each unique index covers active members only, so a removed
-- member keeps its name and origin for the record without holding them against anyone.
-- members.wake_command stays as a column: a checkout needs a machine, and the local
-- opener makes that, not a migration. Naming moves the command and sets it to null.
-- checkouts: one copy of a repo on one machine, with the Context Forge project id
-- that machine knows it by. A member has one per machine and clone.

ALTER TABLE members ADD COLUMN name TEXT COLLATE NOCASE;

ALTER TABLE members ADD COLUMN origin TEXT;

CREATE UNIQUE INDEX members_active_name ON members (name) WHERE removed_at IS NULL;

CREATE UNIQUE INDEX members_active_origin ON members (origin) WHERE removed_at IS NULL;

CREATE TRIGGER members_name_required BEFORE INSERT ON members
WHEN NEW.name IS NULL
BEGIN
    SELECT RAISE(ABORT, 'members: name is required; a member is made with a name');
END;

CREATE TABLE checkouts (
    checkout_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id     TEXT NOT NULL REFERENCES members (project_id),
    machine_id    INTEGER NOT NULL REFERENCES machines (machine_id),
    cf_project_id TEXT NOT NULL,
    path          TEXT NOT NULL,
    wake_command  TEXT,
    owner_id      INTEGER REFERENCES owners (owner_id),
    added_at      TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (machine_id, cf_project_id)
);

CREATE INDEX checkouts_member ON checkouts (member_id);

CREATE TRIGGER checkouts_owner_required BEFORE INSERT ON checkouts
WHEN NEW.owner_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'checkouts: owner_id is required; the store has no acting machine');
END;
