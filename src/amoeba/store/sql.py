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
#: Off only around a migration, which may rebuild a referenced table (228 D3).
PRAGMA_FOREIGN_KEYS_OFF: Final = "PRAGMA foreign_keys=OFF"
PRAGMA_FOREIGN_KEY_CHECK: Final = "PRAGMA foreign_key_check"

# --- relocating a store (store/relocate.py) ---------------------------------

PRAGMA_INTEGRITY_CHECK: Final = "PRAGMA integrity_check"
INTEGRITY_CHECK_OK: Final = "ok"
#: Every ordinary table, leaving out SQLite's own (``sqlite_sequence`` and the like).
SELECT_USER_TABLE_NAMES: Final = (
    "SELECT name FROM sqlite_master WHERE type = 'table' "
    "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name"
)
#: ``resume_log`` values naming a path under a directory: the directory itself or
#: anything below it. Parameters: the directory, then the directory with a trailing
#: separator, twice (``substr`` rather than ``LIKE``, whose wildcards a path may hold).
_RESUME_LOG_UNDER: Final = "(resume_log = ? OR substr(resume_log, 1, length(?)) = ?)"
COUNT_RESUME_LOGS_UNDER: Final = (
    f"SELECT COUNT(*) FROM answers WHERE {_RESUME_LOG_UNDER}"
)
REWRITE_RESUME_LOGS_UNDER: Final = f"""
UPDATE answers SET resume_log = ? || substr(resume_log, length(?) + 1)
WHERE {_RESUME_LOG_UNDER}
"""


def count_rows(table: str) -> str:
    """``SELECT COUNT(*)`` for a table named by ``sqlite_master``, identifier-quoted."""
    return f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34) * 2)}"'


def select_all_rows(table: str) -> str:
    """``SELECT *`` for a table named by ``sqlite_master``, identifier-quoted."""
    return f'SELECT * FROM "{table.replace(chr(34), chr(34) * 2)}"'


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
SELECT_PROGRAMS: Final = f"SELECT {_PROGRAM_COLUMNS} FROM programs ORDER BY program_id"
SELECT_PROGRAM: Final = f"SELECT {_PROGRAM_COLUMNS} FROM programs WHERE program_id = ?"
INSERT_PROGRAM: Final = (
    f"INSERT INTO programs ({_PROGRAM_COLUMNS}) VALUES (?, ?, ?, ?, ?)"
)
UPDATE_PROGRAM: Final = """
UPDATE programs SET concept_member = ?, concept_path = ?, updated_at = ?
WHERE program_id = ?
"""

# --- members ----------------------------------------------------------------

_MEMBER_INSERT_COLUMNS: Final = (
    "project_id, program_id, rules_paths, authorize_allow, authorize_deny, "
    "registered_at, updated_at, rules_from"
)
#: Select order: ``store.programs._member`` reads these positionally.
_MEMBER_COLUMNS: Final = (
    "project_id, program_id, rules_paths, authorize_allow, authorize_deny, "
    "registered_at, updated_at, removed_at, rules_from"
)
#: The active-member predicate (228 D8), the one place "a removed member is not a
#: member" is written. Every member and pair read below uses it.
ACTIVE_MEMBER: Final = "removed_at IS NULL"
SELECT_MEMBER: Final = (
    f"SELECT {_MEMBER_COLUMNS} FROM members WHERE project_id = ? AND {ACTIVE_MEMBER}"
)
#: Reads removed members too: tells a past member from a stranger, and feeds the upsert.
SELECT_MEMBER_ANY: Final = f"SELECT {_MEMBER_COLUMNS} FROM members WHERE project_id = ?"
SELECT_MEMBERS_OF: Final = (
    f"SELECT {_MEMBER_COLUMNS} FROM members WHERE program_id = ? "
    f"AND {ACTIVE_MEMBER} ORDER BY project_id"
)
INSERT_MEMBER: Final = (
    f"INSERT INTO members ({_MEMBER_INSERT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)
UPDATE_MEMBER: Final = """
UPDATE members SET rules_paths = ?, rules_from = ?, authorize_allow = ?,
    authorize_deny = ?, updated_at = ?
WHERE project_id = ?
"""
# Re-registering a removed member: a fresh registration, possibly in another program.
REREGISTER_MEMBER: Final = """
UPDATE members SET program_id = ?, rules_paths = ?, rules_from = ?,
    authorize_allow = ?, authorize_deny = ?, registered_at = ?, updated_at = ?,
    removed_at = NULL
WHERE project_id = ?
"""
REMOVE_MEMBER: Final = (
    "UPDATE members SET removed_at = ?, updated_at = ? "
    f"WHERE project_id = ? AND {ACTIVE_MEMBER}"
)

# --- dependency_pairs -------------------------------------------------------

_PAIR_COLUMNS: Final = (
    "program_id, provider_id, consumer_id, consumed, registered_at, updated_at"
)
# A pair is read only while both its ends are active members. ``remove_member``
# deletes a removed member's pairs, so this holds the rule a second way.
_PAIR_ENDS_ACTIVE: Final = (
    "provider_id IN (SELECT project_id FROM members "
    f"WHERE {ACTIVE_MEMBER}) AND consumer_id IN "
    f"(SELECT project_id FROM members WHERE {ACTIVE_MEMBER})"
)
SELECT_PAIRS_OF: Final = (
    f"SELECT {_PAIR_COLUMNS} FROM dependency_pairs WHERE program_id = ? "
    f"AND {_PAIR_ENDS_ACTIVE} ORDER BY provider_id, consumer_id"
)
SELECT_PAIRS_CONSUMED_BY: Final = (
    f"SELECT {_PAIR_COLUMNS} FROM dependency_pairs WHERE consumer_id = ? "
    f"AND {_PAIR_ENDS_ACTIVE} ORDER BY provider_id"
)
SELECT_PAIR: Final = (
    f"SELECT {_PAIR_COLUMNS} FROM dependency_pairs "
    f"WHERE provider_id = ? AND consumer_id = ? AND {_PAIR_ENDS_ACTIVE}"
)
DELETE_PAIR: Final = (
    "DELETE FROM dependency_pairs WHERE provider_id = ? AND consumer_id = ?"
)
DELETE_PAIRS_OF_MEMBER: Final = (
    "DELETE FROM dependency_pairs WHERE provider_id = ? OR consumer_id = ?"
)
INSERT_PAIR: Final = (
    f"INSERT INTO dependency_pairs ({_PAIR_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)"
)
UPDATE_PAIR: Final = """
UPDATE dependency_pairs SET consumed = ?, updated_at = ?
WHERE provider_id = ? AND consumer_id = ?
"""

# --- releases (slice 227, D2, D3) ---------------------------------------------

RELEASE_COLUMNS: Final = (
    "seq, commit_sha, version, changed, touched, reported_at, versioned_at"
)
SELECT_RELEASE_FOR_COMMIT: Final = (
    f"SELECT {RELEASE_COLUMNS} FROM releases WHERE member_id = ? AND commit_sha = ?"
)
# Parameters: member, commit, version, changed, touched, reported_at, versioned_at.
INSERT_RELEASE: Final = """
INSERT INTO releases
    (member_id, commit_sha, version, changed, touched, reported_at, versioned_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""
# Parameters: version, versioned_at, changed, touched, member, commit.
VERSION_RELEASE: Final = """
UPDATE releases SET version = ?, versioned_at = ?, changed = ?, touched = ?
WHERE member_id = ? AND commit_sha = ?
"""
# A given version replaces the stored one; ``versioned_at`` moves with the correction
# whenever the row holds a version afterwards. SQLite evaluates every SET expression
# against the old row, so the version expression is written twice. Parameters:
# changed, touched, version, reported_at, version, versioned_at, member, commit.
CORRECT_RELEASE: Final = """
UPDATE releases
SET changed = ?, touched = ?, version = COALESCE(?, version), reported_at = ?,
    versioned_at = CASE WHEN COALESCE(?, version) IS NOT NULL THEN ? ELSE NULL END
WHERE member_id = ? AND commit_sha = ?
"""
DELETE_RELEASE: Final = "DELETE FROM releases WHERE member_id = ? AND commit_sha = ?"
# A ``from_source`` consumer sees a report from when it was made or last corrected.
SELECT_RELEASES_FROM_SOURCE: Final = (
    f"SELECT {RELEASE_COLUMNS} FROM releases WHERE member_id = ? AND reported_at >= ? "
    "ORDER BY reported_at, seq"
)
# A ``from_release`` consumer sees a report from when it was versioned.
SELECT_RELEASES_FROM_RELEASE: Final = (
    f"SELECT {RELEASE_COLUMNS} FROM releases "
    "WHERE member_id = ? AND version IS NOT NULL AND versioned_at >= ? "
    "ORDER BY versioned_at, seq"
)

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

QUESTION_COLUMNS: Final = """run_id, paused_at, member_id, question, checkout, state,
    answering_run_id, waiting_reason, waiting_detail, slice_label, source_commit,
    passages, evidence, claimed_at, updated_at, closed_reason, closed_detail,
    closed_at"""
SELECT_QUESTION: Final = (
    f"SELECT {QUESTION_COLUMNS} FROM questions WHERE run_id = ? AND paused_at = ?"
)
SELECT_LATEST_QUESTION: Final = f"""
SELECT {QUESTION_COLUMNS} FROM questions WHERE run_id = ?
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

# --- the question lifecycle (slice 228, D4 to D6) ---------------------------

# Every close is a compare-and-set on the row's state and ``updated_at``: the row
# count tells the caller whether it won. Parameters: closed state, reason, detail,
# closed_at, updated_at, run id, paused_at, expected state, expected updated_at.
CLOSE_QUESTION: Final = """
UPDATE questions SET state = ?, closed_reason = ?, closed_detail = ?,
    closed_at = ?, updated_at = ?
WHERE run_id = ? AND paused_at = ? AND state = ? AND updated_at = ?
"""
# A question is open when it is claimed or waiting on the PM, or answered with its
# latest answer unresumed (resume outcome null or refused). Parameters: claimed,
# waiting_on_pm, answered, refused.
_OPEN_QUESTION_CLAUSE: Final = """(
    questions.state IN (?, ?)
    OR (questions.state = ?
        AND EXISTS (
            SELECT 1 FROM answers AS latest
            WHERE latest.run_id = questions.run_id
                AND latest.paused_at = questions.paused_at
                AND latest.seq = (
                    SELECT MAX(any_answer.seq) FROM answers AS any_answer
                    WHERE any_answer.run_id = questions.run_id
                        AND any_answer.paused_at = questions.paused_at)
                AND (latest.resume_outcome IS NULL OR latest.resume_outcome = ?))))"""
_OPEN_ORDER: Final = " ORDER BY questions.claimed_at, questions.rowid"
SELECT_OPEN_ROWS_OF_RUN: Final = (
    f"SELECT {QUESTION_COLUMNS} FROM questions WHERE questions.run_id = ? "
    f"AND {_OPEN_QUESTION_CLAUSE}{_OPEN_ORDER}"
)
SELECT_OPEN_ROWS_OF_MEMBER: Final = (
    f"SELECT {QUESTION_COLUMNS} FROM questions WHERE questions.member_id = ? "
    f"AND {_OPEN_QUESTION_CLAUSE}{_OPEN_ORDER}"
)

# What ``prune`` needs: the answering run ids and the run ids of open questions.
SELECT_OPEN_ANSWERING_RUN_IDS: Final = (
    "SELECT DISTINCT questions.answering_run_id FROM questions "
    f"WHERE questions.answering_run_id IS NOT NULL AND {_OPEN_QUESTION_CLAUSE}"
)
SELECT_RUN_IDS_WITH_OPEN_QUESTION: Final = (
    f"SELECT DISTINCT questions.run_id FROM questions WHERE {_OPEN_QUESTION_CLAUSE}"
)


def select_open_rows_of_members(member_count: int) -> str:
    """Every open row of the members, oldest first."""
    return (
        f"SELECT {QUESTION_COLUMNS} FROM questions WHERE questions.member_id "
        f"IN ({placeholders(member_count)}) AND {_OPEN_QUESTION_CLAUSE}{_OPEN_ORDER}"
    )


ANSWER_COLUMNS: Final = """seq, run_id, paused_at, answered_by, answer, cited,
    recorded_at, resume_outcome, resume_detail, resume_log, resume_at, retracted_at,
    retract_reason, resume_started_at, via"""
SELECT_ANSWERS_OF: Final = (
    f"SELECT {ANSWER_COLUMNS} FROM answers WHERE run_id = ? AND paused_at = ? "
    "ORDER BY seq"
)
SELECT_ANSWER: Final = f"SELECT {ANSWER_COLUMNS} FROM answers WHERE seq = ?"
SELECT_LATEST_ANSWER: Final = (
    f"SELECT {ANSWER_COLUMNS} FROM answers WHERE run_id = ? AND paused_at = ? "
    "ORDER BY seq DESC LIMIT 1"
)
# Automatic answers since the PM last answered the run (228 D7): a PM answer resets
# the limit, a retracted one included (the run did receive it). Parameters: run id,
# the automatic answerer, run id, the PM.
COUNT_AUTOMATIC_ANSWERS: Final = """
SELECT COUNT(*) FROM answers
WHERE run_id = ? AND answered_by = ?
    AND seq > COALESCE(
        (SELECT MAX(seq) FROM answers WHERE run_id = ? AND answered_by = ?), 0)
"""
INSERT_RECORDED_ANSWER: Final = """
INSERT INTO answers (run_id, paused_at, answered_by, answer, cited, recorded_at,
    via)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""
# ``resumed`` and ``not_delivered`` are final; only ``refused`` may be retried.
RECORD_RESUME: Final = """
UPDATE answers SET resume_outcome = ?, resume_detail = ?, resume_log = ?,
    resume_at = ?
WHERE seq = ? AND (resume_outcome IS NULL OR resume_outcome = ?)
"""
# Retraction is set once (228 D6). Parameters: retracted_at, reason, seq.
RETRACT_ANSWER: Final = """
UPDATE answers SET retracted_at = ?, retract_reason = ?
WHERE seq = ? AND retracted_at IS NULL
"""
# Both compare-and-set on an outcome that is not final (null or refused).
# Parameters: started_at, seq, refused.
MARK_RESUME_STARTED: Final = """
UPDATE answers SET resume_started_at = ?
WHERE seq = ? AND (resume_outcome IS NULL OR resume_outcome = ?)
"""
# Parameters: not_delivered, detail, resume_at, seq, refused. ``resume_log`` stays
# as an earlier refused resume left it.
MARK_NOT_DELIVERED: Final = """
UPDATE answers SET resume_outcome = ?, resume_detail = ?, resume_at = ?
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
    AND answer_row.retracted_at IS NULL
    AND question_row.state <> ?
ORDER BY answer_row.seq
"""


# --- decisions and the PM's marker (slice 224) -------------------------------


def _qualified(columns: str, alias: str) -> str:
    return ", ".join(f"{alias}.{name.strip()}" for name in columns.split(","))


# Each answer joined to its question and the member's program: the answer columns,
# the question columns, the program id, then the newest earlier answer's seq.
_SELECT_DECISIONS: Final = f"""
SELECT {_qualified(ANSWER_COLUMNS, "answer_row")},
    {_qualified(QUESTION_COLUMNS, "question_row")},
    member_row.program_id,
    (SELECT MAX(earlier.seq) FROM answers AS earlier
     WHERE earlier.run_id = answer_row.run_id
         AND earlier.paused_at = answer_row.paused_at
         AND earlier.seq < answer_row.seq)
FROM answers AS answer_row
JOIN questions AS question_row
    ON question_row.run_id = answer_row.run_id
    AND question_row.paused_at = answer_row.paused_at
JOIN members AS member_row ON member_row.project_id = question_row.member_id
"""
DECISIONS_ORDER: Final = " ORDER BY answer_row.seq"
DECISIONS_PROGRAM_CLAUSE: Final = " AND member_row.program_id = ?"
SELECT_DECISIONS_AFTER_SEQ: Final = f"{_SELECT_DECISIONS} WHERE answer_row.seq > ?"
SELECT_DECISIONS_SINCE: Final = f"{_SELECT_DECISIONS} WHERE answer_row.recorded_at >= ?"
# Questions that ended at or after a time (229 D3): closed ones by ``closed_at``,
# answered ones whose newest answer was handed over (resumed) or can no longer be
# (not delivered) by that answer's ``recorded_at``. Parameters: closed state, since,
# answered state, since, resumed, not delivered. Keeps removed members: the record.
SELECT_SETTLED_SINCE: Final = """
SELECT member_row.program_id, question_row.member_id, question_row.run_id,
    question_row.paused_at, question_row.question,
    question_row.closed_reason, question_row.closed_at
FROM questions AS question_row
JOIN members AS member_row ON member_row.project_id = question_row.member_id
WHERE question_row.state = ? AND question_row.closed_at >= ?
UNION ALL
SELECT member_row.program_id, question_row.member_id, question_row.run_id,
    question_row.paused_at, question_row.question,
    answer_row.answered_by, answer_row.recorded_at
FROM questions AS question_row
JOIN members AS member_row ON member_row.project_id = question_row.member_id
JOIN answers AS answer_row
    ON answer_row.run_id = question_row.run_id
    AND answer_row.paused_at = question_row.paused_at
WHERE question_row.state = ? AND answer_row.recorded_at >= ?
    AND answer_row.resume_outcome IN (?, ?)
    AND answer_row.seq = (SELECT MAX(latest.seq) FROM answers AS latest
                          WHERE latest.run_id = answer_row.run_id
                              AND latest.paused_at = answer_row.paused_at)
ORDER BY 7 DESC, 3, 4
"""
SELECT_MARKER: Final = "SELECT last_seen_seq FROM pm_marker WHERE id = 1"
SELECT_MAX_ANSWER_SEQ: Final = "SELECT COALESCE(MAX(seq), 0) FROM answers"
RAISE_MARKER: Final = """
UPDATE pm_marker SET last_seen_seq = MAX(last_seen_seq, ?) WHERE id = 1
"""


# --- reads for ``status`` (slice 224, D4) ------------------------------------


def placeholders(count: int) -> str:
    """``count`` bound-parameter marks for an ``IN`` list; never values."""
    if count < 1:
        raise ValueError("an IN list needs at least one value")
    return ", ".join("?" * count)


def select_open_questions(member_count: int) -> str:
    """Every ``waiting_on_pm`` question of the members, oldest first."""
    return (
        f"SELECT {QUESTION_COLUMNS} FROM questions "
        f"WHERE state = ? AND member_id IN ({placeholders(member_count)}) "
        "ORDER BY claimed_at, rowid"
    )


def select_member_questions(member_count: int) -> str:
    """Every question of the members, oldest first, so the last of a run is its
    latest."""
    return (
        f"SELECT {QUESTION_COLUMNS} FROM questions "
        f"WHERE member_id IN ({placeholders(member_count)}) "
        "ORDER BY claimed_at, rowid"
    )


def select_answers_of_runs(run_count: int) -> str:
    """Every answer of the runs, in ``seq`` order."""
    return (
        f"SELECT {ANSWER_COLUMNS} FROM answers "
        f"WHERE run_id IN ({placeholders(run_count)}) ORDER BY seq"
    )
