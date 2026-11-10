-- Baseline schema (slice 222, D3). Member ids are Context Forge project ids; times
-- are UTC ISO-8601 text. Never edit this file: later migrations only add columns.
-- Every CHECK list below is pinned to its enum by tests/store/test_vocabulary_pinning.py.

CREATE TABLE schema_meta (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE programs (
    program_id     TEXT PRIMARY KEY,
    concept_member TEXT,
    concept_path   TEXT,
    registered_at  TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    CHECK ((concept_member IS NULL) = (concept_path IS NULL))
);

CREATE TABLE members (
    project_id      TEXT PRIMARY KEY,
    program_id      TEXT NOT NULL REFERENCES programs (program_id),
    rules_paths     TEXT NOT NULL,
    authorize_allow TEXT NOT NULL,
    authorize_deny  TEXT NOT NULL,
    registered_at   TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (program_id, project_id)
);

CREATE TABLE dependency_pairs (
    program_id    TEXT NOT NULL,
    provider_id   TEXT NOT NULL,
    consumer_id   TEXT NOT NULL,
    consumed      TEXT NOT NULL CHECK (consumed IN ('from_source', 'from_release')),
    registered_at TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (provider_id, consumer_id),
    FOREIGN KEY (program_id, provider_id) REFERENCES members (program_id, project_id),
    FOREIGN KEY (program_id, consumer_id) REFERENCES members (program_id, project_id),
    CHECK (provider_id <> consumer_id)
);

CREATE TABLE releases (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id    TEXT NOT NULL REFERENCES members (project_id),
    commit_sha   TEXT NOT NULL,
    version      TEXT,
    changed      TEXT NOT NULL,
    touched      TEXT NOT NULL,
    reported_at  TEXT NOT NULL,
    versioned_at TEXT,
    UNIQUE (member_id, commit_sha)
);

CREATE TABLE questions (
    run_id           TEXT NOT NULL,
    paused_at        TEXT NOT NULL,
    member_id        TEXT NOT NULL REFERENCES members (project_id),
    question         TEXT NOT NULL,
    checkout         TEXT NOT NULL,
    state            TEXT NOT NULL
        CHECK (state IN ('claimed', 'answered', 'waiting_on_pm')),
    answering_run_id TEXT,
    waiting_reason   TEXT,
    claimed_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (run_id, paused_at)
);

CREATE TABLE answers (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT NOT NULL,
    paused_at      TEXT NOT NULL,
    answered_by    TEXT NOT NULL CHECK (answered_by IN ('answerer', 'pm')),
    answer         TEXT NOT NULL,
    recorded_at    TEXT NOT NULL,
    resume_outcome TEXT
        CHECK (resume_outcome IS NULL
               OR resume_outcome IN ('resumed', 'refused', 'not_delivered')),
    FOREIGN KEY (run_id, paused_at) REFERENCES questions (run_id, paused_at)
);

CREATE TABLE pm_marker (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    last_seen_seq INTEGER NOT NULL
);

INSERT INTO pm_marker (id, last_seen_seq) VALUES (1, 0);
