-- Migration 003: the command journal.
--
-- An entry is written and committed BEFORE a side-effecting command is issued,
-- and closed when its result arrives. An entry whose outcome is still NULL is
-- therefore a command that may or may not have reached the external system --
-- exactly what recovery reconciles by observation on the next start.
--
-- This is the first real use of the numbered-migration mechanism; 002 was
-- deliberately trivial so the mechanism was proved before a schema change
-- depended on it. Column names here must match the constants in sql_journal.py,
-- which is the single definition site.

CREATE TABLE command_journal (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    node_id TEXT NOT NULL REFERENCES nodes (id),
    kind TEXT NOT NULL,
    -- Stored verbatim as JSON text. Shown by `amoeba inspect`, so callers must
    -- not place secrets here; the contract documents states this.
    parameters TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    -- NULL while unresolved. The nullability IS the in-flight state: this
    -- column is what recovery queries on.
    outcome TEXT,
    result TEXT,
    resolved_at TEXT,
    resolved_by TEXT
);

-- Serves the recovery query -- unresolved entries for one project, oldest
-- first. Partial, because recovery never looks at resolved entries and the
-- resolved rows accumulate without bound (retention is Future Work).
CREATE INDEX idx_command_journal_unresolved
    ON command_journal (project_id, issued_at)
    WHERE outcome IS NULL;

-- Serves the inspection listing, which is project-scoped and may include
-- resolved entries.
CREATE INDEX idx_command_journal_project
    ON command_journal (project_id, issued_at);
