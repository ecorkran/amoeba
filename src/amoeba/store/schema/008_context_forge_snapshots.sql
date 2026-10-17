-- Migration 008: Context Forge links and snapshots.
--
-- Column names here must match the constants in sql_cf.py, the single
-- definition site. Nothing to backfill.
--
-- No CHECK constraint on outcome: the word list is defined once, in
-- cf_models.py, and the row mapping raises on an unknown value.

-- A Context Forge project an Amoeba project watches. Configuration, not an
-- event: no trigger (as review_watches in 006). A link is permanent.
CREATE TABLE cf_links (
    project_id TEXT NOT NULL,
    cf_project_id TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    PRIMARY KEY (project_id, cf_project_id)
);

-- Append-only. A row is written only when something changed (108, D3).
CREATE TABLE cf_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    cf_project_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    -- JSON text; NULL unless the outcome is observed.
    state TEXT,
    -- JSON array text; NULL unless the outcome is observed.
    changed TEXT,
    -- NULL when observed.
    detail TEXT,
    -- CF's own updatedAt, copied as given; provenance, never compared.
    cf_updated_at TEXT,
    cf_version_label TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

CREATE INDEX idx_cf_snapshots_link
    ON cf_snapshots (project_id, cf_project_id, id);

-- One change per snapshot, for every outcome. The kind literal mirrors
-- ChangeKind.CF_PROJECT_CHANGED in feed_models.py; the invariant test
-- (tests/store/test_feed_invariant.py) fails if it drifts. The outcome words are
-- not repeated: the payload carries whatever the row holds. changed is NULL for
-- a failure, so the payload's changed is JSON null; the detail stays on the row,
-- read by subject_id.
CREATE TRIGGER changes_cf_project_changed
AFTER INSERT ON cf_snapshots
BEGIN
    INSERT INTO changes (project_id, kind, node_id, subject_id, payload, recorded_at)
    VALUES (
        new.project_id,
        'cf_project_changed',
        NULL,
        new.id,
        json_object(
            'cf_project_id', new.cf_project_id,
            'outcome', new.outcome,
            'changed', json(new.changed)
        ),
        new.observed_at
    );
END;
