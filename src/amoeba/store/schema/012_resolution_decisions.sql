-- Migration 012: resolution decisions and the Runner's answer (slice 127, D9).
--
-- The column and index names here must match the COL_BLOCKED_* and
-- INDEX_BLOCKED_AWAITS_RUNNER constants in sql.py, the single definition site.
-- Nothing to backfill: existing rows read null in every new column.
-- resolution_decision and resolution_instructions come from the PM's submission.
-- awaits_runner = 1 means a PM resolution the Runner has not yet answered; the
-- Runner's acknowledgment clears it to null and fills the three runner_* columns
-- (runner_outcome is 'applied' or 'rejected').

ALTER TABLE blocked_states ADD COLUMN resolution_decision TEXT;
ALTER TABLE blocked_states ADD COLUMN resolution_instructions TEXT;
ALTER TABLE blocked_states ADD COLUMN awaits_runner INTEGER;
ALTER TABLE blocked_states ADD COLUMN runner_outcome TEXT;
ALTER TABLE blocked_states ADD COLUMN runner_code TEXT;
ALTER TABLE blocked_states ADD COLUMN runner_reason TEXT;

CREATE INDEX idx_blocked_states_awaits_runner
    ON blocked_states (resolved_at) WHERE awaits_runner = 1;
