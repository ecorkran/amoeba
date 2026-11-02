-- Migration 014: the reserved term on a question record (slice 142, D9).
--
-- Set only when the answer gate declined an answer for containing a PM-reserved
-- term (decline_reason 'reserved_term'); it holds the term as configured. Null
-- on every other row, existing ones included, so nothing to backfill. The column
-- name must match COL_QUESTION_RESERVED_TERM in sql_questions.py.

ALTER TABLE question_records ADD COLUMN reserved_term TEXT;
