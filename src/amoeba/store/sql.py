"""Every SQL statement the store runs, spelled once.

Values are always bound parameters. The transaction statements live here so that
``Store.write()`` and ``migrate()`` share one definition of the write lock.
"""

from __future__ import annotations

from typing import Final

# --- connection and transactions -------------------------------------------

#: Takes the write lock up front: a deferred read-then-write can hit SQLITE_BUSY
#: without waiting for the busy timeout.
BEGIN_IMMEDIATE: Final = "BEGIN IMMEDIATE"
BEGIN_DEFERRED: Final = "BEGIN"
COMMIT: Final = "COMMIT"
ROLLBACK: Final = "ROLLBACK"
PRAGMA_JOURNAL_MODE_WAL: Final = "PRAGMA journal_mode=WAL"
PRAGMA_FOREIGN_KEYS_ON: Final = "PRAGMA foreign_keys=ON"

# --- schema_meta ------------------------------------------------------------

TABLE_SCHEMA_META: Final = "schema_meta"
SCHEMA_META_ROW_ID: Final = 1
SELECT_TABLE_EXISTS: Final = (
    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?"
)
SELECT_SCHEMA_VERSION: Final = "SELECT version FROM schema_meta WHERE id = ?"
UPSERT_SCHEMA_VERSION: Final = """
INSERT INTO schema_meta (id, version) VALUES (?, ?)
ON CONFLICT (id) DO UPDATE SET version = excluded.version
"""

# --- programs ---------------------------------------------------------------

_PROGRAM_COLUMNS: Final = (
    "program_id, concept_member, concept_path, registered_at, updated_at"
)
SELECT_PROGRAM: Final = f"SELECT {_PROGRAM_COLUMNS} FROM programs WHERE program_id = ?"
INSERT_PROGRAM: Final = (
    f"INSERT INTO programs ({_PROGRAM_COLUMNS}) VALUES (?, ?, ?, ?, ?)"
)
UPDATE_PROGRAM: Final = """
UPDATE programs SET concept_member = ?, concept_path = ?, updated_at = ?
WHERE program_id = ?
"""

# --- members ----------------------------------------------------------------

_MEMBER_COLUMNS: Final = (
    "project_id, program_id, rules_paths, authorize_allow, authorize_deny, "
    "registered_at, updated_at"
)
SELECT_MEMBER: Final = f"SELECT {_MEMBER_COLUMNS} FROM members WHERE project_id = ?"
SELECT_MEMBERS_OF: Final = (
    f"SELECT {_MEMBER_COLUMNS} FROM members WHERE program_id = ? ORDER BY project_id"
)
INSERT_MEMBER: Final = (
    f"INSERT INTO members ({_MEMBER_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)"
)
UPDATE_MEMBER: Final = """
UPDATE members SET rules_paths = ?, authorize_allow = ?, authorize_deny = ?,
    updated_at = ?
WHERE project_id = ?
"""

# --- dependency_pairs -------------------------------------------------------

_PAIR_COLUMNS: Final = (
    "program_id, provider_id, consumer_id, consumed, registered_at, updated_at"
)
SELECT_PAIRS_OF: Final = (
    f"SELECT {_PAIR_COLUMNS} FROM dependency_pairs WHERE program_id = ? "
    "ORDER BY provider_id, consumer_id"
)
SELECT_PAIR: Final = (
    f"SELECT {_PAIR_COLUMNS} FROM dependency_pairs "
    "WHERE provider_id = ? AND consumer_id = ?"
)
INSERT_PAIR: Final = (
    f"INSERT INTO dependency_pairs ({_PAIR_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)"
)
UPDATE_PAIR: Final = """
UPDATE dependency_pairs SET consumed = ?, updated_at = ?
WHERE provider_id = ? AND consumer_id = ?
"""

# --- questions and answers (written by slice 223) ---------------------------

# Seeding statements: the slice 222 columns only, kept for tests that state a row.
INSERT_QUESTION: Final = """
INSERT INTO questions (run_id, paused_at, member_id, question, checkout, state,
    answering_run_id, waiting_reason, claimed_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
INSERT_ANSWER: Final = """
INSERT INTO answers (run_id, paused_at, answered_by, answer, recorded_at,
    resume_outcome)
VALUES (?, ?, ?, ?, ?, ?)
"""

_QUESTION_COLUMNS: Final = """run_id, paused_at, member_id, question, checkout, state,
    answering_run_id, waiting_reason, waiting_detail, slice_label, source_commit,
    passages, evidence, claimed_at, updated_at"""
SELECT_QUESTION: Final = (
    f"SELECT {_QUESTION_COLUMNS} FROM questions WHERE run_id = ? AND paused_at = ?"
)
SELECT_LATEST_QUESTION: Final = f"""
SELECT {_QUESTION_COLUMNS} FROM questions WHERE run_id = ?
ORDER BY claimed_at DESC, rowid DESC LIMIT 1
"""
SELECT_ANSWERING_RUN_EXISTS: Final = (
    "SELECT 1 FROM questions WHERE answering_run_id = ? LIMIT 1"
)
SELECT_QUESTION_CLAIM: Final = (
    "SELECT state, answering_run_id FROM questions WHERE run_id = ? AND paused_at = ?"
)
# A lost race inserts nothing: the caller learns it from the row count.
INSERT_NEW_QUESTION: Final = """
INSERT INTO questions (run_id, paused_at, member_id, question, checkout, state,
    answering_run_id, waiting_reason, waiting_detail, slice_label, source_commit,
    passages, claimed_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (run_id, paused_at) DO NOTHING
"""
# Every move out of ``claimed`` names the claim it holds (D4). The state values are
# bound parameters (from ``QuestionState``), so no vocabulary is spelled here.
SETTLE_WAITING: Final = """
UPDATE questions SET state = ?, waiting_reason = ?, waiting_detail = ?,
    evidence = ?, updated_at = ?
WHERE run_id = ? AND paused_at = ? AND state = ? AND answering_run_id = ?
"""
SETTLE_ANSWERED: Final = """
UPDATE questions SET state = ?, evidence = ?, updated_at = ?
WHERE run_id = ? AND paused_at = ? AND state = ? AND answering_run_id = ?
"""
REPLACE_CLAIM: Final = """
UPDATE questions SET answering_run_id = ?, passages = ?, updated_at = ?
WHERE run_id = ? AND paused_at = ? AND state = ? AND answering_run_id = ?
"""
MARK_QUESTION_ANSWERED: Final = """
UPDATE questions SET state = ?, updated_at = ? WHERE run_id = ? AND paused_at = ?
"""

_ANSWER_COLUMNS: Final = """seq, run_id, paused_at, answered_by, answer, cited,
    recorded_at, resume_outcome, resume_detail, resume_log, resume_at"""
SELECT_ANSWERS_OF: Final = (
    f"SELECT {_ANSWER_COLUMNS} FROM answers WHERE run_id = ? AND paused_at = ? "
    "ORDER BY seq"
)
SELECT_LATEST_ANSWER: Final = (
    f"SELECT {_ANSWER_COLUMNS} FROM answers WHERE run_id = ? AND paused_at = ? "
    "ORDER BY seq DESC LIMIT 1"
)
COUNT_AUTOMATIC_ANSWERS: Final = (
    "SELECT COUNT(*) FROM answers WHERE run_id = ? AND answered_by = ?"
)
INSERT_RECORDED_ANSWER: Final = """
INSERT INTO answers (run_id, paused_at, answered_by, answer, cited, recorded_at)
VALUES (?, ?, ?, ?, ?, ?)
"""
# ``resumed`` and ``not_delivered`` are final; only ``refused`` may be retried.
RECORD_RESUME: Final = """
UPDATE answers SET resume_outcome = ?, resume_detail = ?, resume_log = ?,
    resume_at = ?
WHERE seq = ? AND (resume_outcome IS NULL OR resume_outcome = ?)
"""
SELECT_PM_PRECEDENT: Final = """
SELECT question_row.run_id, question_row.paused_at, question_row.question,
    question_row.slice_label, answer_row.seq, answer_row.answer,
    answer_row.recorded_at
FROM questions AS question_row
JOIN answers AS answer_row
    ON answer_row.run_id = question_row.run_id
    AND answer_row.paused_at = question_row.paused_at
WHERE question_row.member_id = ?
    AND answer_row.answered_by = ?
    AND answer_row.seq = (
        SELECT MAX(newer.seq) FROM answers AS newer
        WHERE newer.run_id = question_row.run_id
            AND newer.paused_at = question_row.paused_at
            AND newer.answered_by = ?)
ORDER BY answer_row.seq
"""
