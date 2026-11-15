-- Requests between members (slice 240, D1). Three new tables and their indexes, so
-- no rebuild and no edit to an applied migration. Member ids are Context Forge
-- project ids; times are UTC ISO-8601 text. The CHECK lists on kind, state and event
-- are pinned to MessageKind, RequestState and DeliveryEvent by
-- tests/store/test_vocabulary_pinning.py.
--
-- 'note' and to_program are here now because SQLite cannot widen a CHECK in place and
-- 243 has no migration; 240 writes only requests. parent_id is not a foreign key: a
-- terminal parent may be pruned while a child is open, so each message keeps its own
-- depth.

CREATE TABLE messages (
    message_id       TEXT PRIMARY KEY,
    kind             TEXT NOT NULL CHECK (kind IN ('request', 'note')),
    from_member      TEXT NOT NULL REFERENCES members (project_id),
    to_member        TEXT REFERENCES members (project_id),
    to_program       TEXT REFERENCES programs (program_id),
    parent_id        TEXT,
    depth            INTEGER NOT NULL CHECK (depth >= 1),
    subject          TEXT NOT NULL,
    body             TEXT NOT NULL,
    state            TEXT
        CHECK (state IS NULL
               OR state IN ('open', 'accepted', 'done', 'declined', 'cancelled',
                            'expired')),
    result           TEXT,
    result_commit    TEXT,
    result_version   TEXT,
    reason           TEXT,
    accepted_at      TEXT,
    created_at       TEXT NOT NULL,
    state_changed_at TEXT NOT NULL,
    expires_at       TEXT,
    CHECK (
        (kind = 'request'
            AND to_member IS NOT NULL AND to_program IS NULL
            AND state IS NOT NULL AND expires_at IS NOT NULL)
        OR
        (kind = 'note'
            AND (to_member IS NULL) <> (to_program IS NULL)
            AND state IS NULL AND expires_at IS NULL)
    )
);

CREATE INDEX messages_to_member_state ON messages (to_member, state);
CREATE INDEX messages_from_member_state ON messages (from_member, state);
CREATE INDEX messages_parent ON messages (parent_id);
CREATE INDEX messages_state_expires ON messages (state, expires_at);

CREATE TABLE deliveries (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id  TEXT NOT NULL REFERENCES members (project_id),
    message_id TEXT NOT NULL REFERENCES messages (message_id),
    event      TEXT NOT NULL
        CHECK (event IN ('sent', 'accepted', 'declined', 'done', 'cancelled',
                         'expired')),
    created_at TEXT NOT NULL
);

CREATE INDEX deliveries_member_seq ON deliveries (member_id, seq);
-- Not in D1: the prune deletes a request's deliveries by message_id, and the
-- foreign-key check on messages looks them up the same way.
CREATE INDEX deliveries_message ON deliveries (message_id);

-- A send, reply or cancel that was rejected once its caller was known (D9).
-- operation and code hold an OperationName and a RejectCode value with no CHECK, so
-- a new code is not a migration.
CREATE TABLE message_rejections (
    id         INTEGER PRIMARY KEY,
    member_id  TEXT NOT NULL REFERENCES members (project_id),
    operation  TEXT NOT NULL,
    to_ref     TEXT,
    message_id TEXT,
    parent_id  TEXT,
    code       TEXT NOT NULL,
    detail     TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX message_rejections_created ON message_rejections (created_at);
