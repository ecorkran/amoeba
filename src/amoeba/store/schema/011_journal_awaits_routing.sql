-- Migration 011: a resolved sq_run awaits routing (slice 125, D8).
--
-- The column and index names here must match COL_JOURNAL_AWAITS_ROUTING and
-- INDEX_JOURNAL_AWAITS_ROUTING in sql_journal.py, the single definition site.
-- Nothing to backfill: existing rows read null, meaning "not awaiting routing".
-- 1 means a Runner resolution left evidence for the routing engine to decide on;
-- a routing decision sets it back to null.

ALTER TABLE command_journal ADD COLUMN awaits_routing INTEGER;

CREATE INDEX idx_journal_awaits_routing
    ON command_journal (project_id, issued_at) WHERE awaits_routing = 1;
