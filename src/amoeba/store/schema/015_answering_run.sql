-- Migration 015: what an answering run rested on (slice 144, D11).
--
-- Nine nullable columns on question_records. answering_entry_id links the
-- sq_answer journal entry that ran the answerer; at most one record per entry.
-- passage_index and dropped_pm_answers are JSON text; the rest is plain text.
-- Null on every row written before 015, so nothing to backfill. The column
-- names must match the COL_QUESTION_* constants in sql_questions.py.
--
-- decline_reason is free text here: 013 declared no CHECK constraint or lookup
-- table for it, so the new DeclineReason values (slice 144, D8) need no rebuild.

ALTER TABLE question_records
    ADD COLUMN answering_entry_id TEXT REFERENCES command_journal (id);
ALTER TABLE question_records ADD COLUMN source_commit TEXT;
ALTER TABLE question_records ADD COLUMN passage_index TEXT;
ALTER TABLE question_records ADD COLUMN dropped_pm_answers TEXT;
ALTER TABLE question_records ADD COLUMN proposed_answer TEXT;
ALTER TABLE question_records ADD COLUMN cited_passages TEXT;
ALTER TABLE question_records ADD COLUMN check_verdict TEXT;
ALTER TABLE question_records ADD COLUMN check_reason TEXT;
ALTER TABLE question_records ADD COLUMN decline_detail TEXT;

CREATE UNIQUE INDEX idx_question_records_answering_entry
    ON question_records (answering_entry_id) WHERE answering_entry_id IS NOT NULL;
