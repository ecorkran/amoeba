-- Standing answers (slice 230, D1). CREATE TABLE only, so existing rows are untouched.
-- Times are UTC ISO-8601 text.
--
-- One row per ruling the PM gave ahead of time. A row is active until withdrawn, and
-- withdrawn is terminal. Rows are never deleted: a delivered answer cites a standing
-- answer as standing:<id>, and this row is where that text stays readable. No index:
-- the table grows only with the PM's rulings. The reach CHECK list is pinned to
-- StandingReach by tests/store/test_vocabulary_pinning.py.

CREATE TABLE standing_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    text            TEXT NOT NULL CHECK (length(trim(text)) > 0),
    reach           TEXT NOT NULL CHECK (reach IN ('all', 'program', 'member')),
    program_id      TEXT REFERENCES programs (program_id),
    member_id       TEXT REFERENCES members (project_id),
    given_at        TEXT NOT NULL,
    withdrawn_at    TEXT,
    withdraw_reason TEXT,
    CHECK ((reach = 'all') = (program_id IS NULL AND member_id IS NULL)),
    CHECK ((reach = 'program') = (program_id IS NOT NULL AND member_id IS NULL)),
    CHECK ((reach = 'member') = (member_id IS NOT NULL)),
    CHECK ((withdrawn_at IS NULL) = (withdraw_reason IS NULL))
);
