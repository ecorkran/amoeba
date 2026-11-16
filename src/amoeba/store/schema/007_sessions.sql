-- Serving amoeba-mcp processes (slice 241, D6). Create-only: one new table and its
-- indexes, so existing rows are untouched. One row per serving process, written by
-- its heartbeat; a row whose heartbeat_at is older than session_stale_seconds counts
-- as gone and is pruned by the next heartbeat of any server. Times are UTC ISO-8601
-- text. No CHECK list, so no vocabulary to pin.

CREATE TABLE sessions (
    session_id        TEXT PRIMARY KEY,
    member_id         TEXT NOT NULL REFERENCES members (project_id),
    client            TEXT NOT NULL,
    directory         TEXT NOT NULL,
    started_at        TEXT NOT NULL,
    heartbeat_at      TEXT NOT NULL,
    push_confirmed_at TEXT
);

CREATE INDEX sessions_member ON sessions (member_id);
CREATE INDEX sessions_heartbeat ON sessions (heartbeat_at);
