-- Program store migration 001: the program record.
--
-- Programs, their members, how each member is consumed, and the record of every
-- program submission. The program store holds no project's nodes, blocks,
-- questions, journal, messages, verdicts, checks, snapshots or feed.
--
-- Vocabularies and the initiative range here are pinned to the enums and
-- constants in program_models.py by tests/store/test_program_schema.py.
--
-- concept_member and override dependents are checked in code inside the apply
-- transaction: a foreign key from programs to program_members would be circular
-- on creation. The UNIQUE on program_members.project_id backs
-- member_of_other_program structurally; the code checks first so the rejection
-- names it.

CREATE TABLE schema_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE programs (
    program_id TEXT PRIMARY KEY,
    concept_member TEXT NOT NULL,
    concept_path TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE program_members (
    program_id TEXT NOT NULL REFERENCES programs (program_id),
    -- One program per project.
    project_id TEXT NOT NULL UNIQUE,
    requests_initiative INTEGER NOT NULL
        CHECK (requests_initiative BETWEEN 100 AND 799),
    consumed TEXT NOT NULL CHECK (consumed IN ('from_source', 'from_release')),
    registered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (program_id, project_id)
);

CREATE TABLE consumption_overrides (
    program_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    dependent_id TEXT NOT NULL,
    consumed TEXT NOT NULL CHECK (consumed IN ('from_source', 'from_release')),
    PRIMARY KEY (program_id, provider_id, dependent_id),
    FOREIGN KEY (program_id, provider_id)
        REFERENCES program_members (program_id, project_id),
    CHECK (provider_id <> dependent_id)
);

CREATE TABLE program_submissions (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    submitted_by TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    applied_seq INTEGER NOT NULL UNIQUE,
    applied_at TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('applied', 'rejected')),
    reason TEXT,
    payload TEXT NOT NULL
);
