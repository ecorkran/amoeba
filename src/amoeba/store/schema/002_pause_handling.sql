-- Pause handling (slice 223, D10). ADD COLUMN only, every column nullable (222 D3).
-- JSON columns are written and read through store/question_json.py.

-- D5's slice label, reused on precedent passages.
ALTER TABLE questions ADD COLUMN slice_label TEXT;
-- The commit the passages were read at.
ALTER TABLE questions ADD COLUMN source_commit TEXT;
-- JSON array of passage references (id, source, question_id, date).
ALTER TABLE questions ADD COLUMN passages TEXT;
-- Bounded detail for waiting_reason.
ALTER TABLE questions ADD COLUMN waiting_detail TEXT;
-- JSON object: proposed answer, citations, check verdict and reason.
ALTER TABLE questions ADD COLUMN evidence TEXT;

-- JSON array of passage ids an automatic answer cites.
ALTER TABLE answers ADD COLUMN cited TEXT;
-- Refusal or not-delivered detail.
ALTER TABLE answers ADD COLUMN resume_detail TEXT;
-- Path of the resume's stdout log.
ALTER TABLE answers ADD COLUMN resume_log TEXT;
-- When the resume outcome was recorded.
ALTER TABLE answers ADD COLUMN resume_at TEXT;
