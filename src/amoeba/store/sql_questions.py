"""Every SQL statement and column name for question records (slice 141).

Sibling of ``sql_runner.py`` under the same rule: a name or statement for
``question_records`` appears here and in migration ``013`` and nowhere else.
Every value is a bound parameter.
"""

from __future__ import annotations

from typing import Final

TABLE_QUESTION_RECORDS: Final = "question_records"

COL_QUESTION_ID: Final = "id"
COL_QUESTION_PROJECT_ID: Final = "project_id"
COL_QUESTION_NODE_ID: Final = "node_id"
COL_QUESTION_SOURCE_ENTRY_ID: Final = "source_entry_id"
COL_QUESTION_RUN_ID: Final = "run_id"
COL_QUESTION_STEP: Final = "step"
COL_QUESTION_TEXT: Final = "question"
COL_QUESTION_TRUNCATED: Final = "truncated"
COL_QUESTION_BLOCKED_STATE_ID: Final = "blocked_state_id"
COL_QUESTION_STATE: Final = "state"
COL_QUESTION_ANSWERED_BY: Final = "answered_by"
COL_QUESTION_ANSWER: Final = "answer"
COL_QUESTION_DECLINE_REASON: Final = "decline_reason"
COL_QUESTION_CREATED_AT: Final = "created_at"
COL_QUESTION_UPDATED_AT: Final = "updated_at"
COL_QUESTION_RESERVED_TERM: Final = "reserved_term"
# Migration 015 (slice 144): what an answering run rested on.
COL_QUESTION_ANSWERING_ENTRY_ID: Final = "answering_entry_id"
COL_QUESTION_SOURCE_COMMIT: Final = "source_commit"
COL_QUESTION_PASSAGE_INDEX: Final = "passage_index"
COL_QUESTION_DROPPED_PM_ANSWERS: Final = "dropped_pm_answers"
COL_QUESTION_PROPOSED_ANSWER: Final = "proposed_answer"
COL_QUESTION_CITED_PASSAGES: Final = "cited_passages"
COL_QUESTION_CHECK_VERDICT: Final = "check_verdict"
COL_QUESTION_CHECK_REASON: Final = "check_reason"
COL_QUESTION_DECLINE_DETAIL: Final = "decline_detail"

#: JSON keys of one ``passage_index`` element. The text is never stored.
PASSAGE_KEY_ID: Final = "id"
PASSAGE_KEY_SOURCE: Final = "source"
PASSAGE_KEY_QUESTION_ID: Final = "question_id"
PASSAGE_KEY_DATE: Final = "date"

#: The migration-015 columns, in column order.
ANSWERING_COLUMNS: Final = (
    COL_QUESTION_ANSWERING_ENTRY_ID,
    COL_QUESTION_SOURCE_COMMIT,
    COL_QUESTION_PASSAGE_INDEX,
    COL_QUESTION_DROPPED_PM_ANSWERS,
    COL_QUESTION_PROPOSED_ANSWER,
    COL_QUESTION_CITED_PASSAGES,
    COL_QUESTION_CHECK_VERDICT,
    COL_QUESTION_CHECK_REASON,
    COL_QUESTION_DECLINE_DETAIL,
)

#: Column order for every question SELECT, the INSERT, and row mapping.
QUESTION_COLUMNS: Final = (
    COL_QUESTION_ID,
    COL_QUESTION_PROJECT_ID,
    COL_QUESTION_NODE_ID,
    COL_QUESTION_SOURCE_ENTRY_ID,
    COL_QUESTION_RUN_ID,
    COL_QUESTION_STEP,
    COL_QUESTION_TEXT,
    COL_QUESTION_TRUNCATED,
    COL_QUESTION_BLOCKED_STATE_ID,
    COL_QUESTION_STATE,
    COL_QUESTION_ANSWERED_BY,
    COL_QUESTION_ANSWER,
    COL_QUESTION_DECLINE_REASON,
    COL_QUESTION_CREATED_AT,
    COL_QUESTION_UPDATED_AT,
    COL_QUESTION_RESERVED_TERM,
    *ANSWERING_COLUMNS,
)

_SELECT_LIST: Final = ", ".join(QUESTION_COLUMNS)
_SELECT_FROM: Final = f"SELECT {_SELECT_LIST} FROM {TABLE_QUESTION_RECORDS}"

INSERT_QUESTION: Final = (
    f"INSERT INTO {TABLE_QUESTION_RECORDS} ({_SELECT_LIST}) "
    f"VALUES ({', '.join('?' for _ in QUESTION_COLUMNS)})"
)

SELECT_QUESTION_BY_ID: Final = f"{_SELECT_FROM} WHERE {COL_QUESTION_ID} = ?"

SELECT_QUESTION_BY_ENTRY: Final = (
    f"{_SELECT_FROM} WHERE {COL_QUESTION_SOURCE_ENTRY_ID} = ?"
)

SELECT_QUESTION_BY_BLOCK: Final = (
    f"{_SELECT_FROM} WHERE {COL_QUESTION_BLOCKED_STATE_ID} = ?"
)

#: Parameters: project, state, node. A null state or node matches every value.
SELECT_QUESTIONS: Final = f"""
{_SELECT_FROM}
WHERE {COL_QUESTION_PROJECT_ID} = ?
  AND (? IS NULL OR {COL_QUESTION_STATE} = ?)
  AND (? IS NULL OR {COL_QUESTION_NODE_ID} = ?)
ORDER BY {COL_QUESTION_CREATED_AT}, {COL_QUESTION_ID}
"""

#: Parameters: project, state. Written as an equality so the
#: ``(project_id, state, created_at)`` index serves it.
SELECT_QUESTIONS_IN_STATE: Final = f"""
{_SELECT_FROM}
WHERE {COL_QUESTION_PROJECT_ID} = ? AND {COL_QUESTION_STATE} = ?
ORDER BY {COL_QUESTION_CREATED_AT}, {COL_QUESTION_ID}
"""

#: Parameters: project, run, state, answered_by, excluded record id. The answers
#: the answerer already gave this run, not counting the record being submitted
#: (slice 142, D3).
COUNT_ANSWERER_ANSWERS_IN_RUN: Final = f"""
SELECT COUNT(*) FROM {TABLE_QUESTION_RECORDS}
WHERE {COL_QUESTION_PROJECT_ID} = ? AND {COL_QUESTION_RUN_ID} = ?
  AND {COL_QUESTION_STATE} = ? AND {COL_QUESTION_ANSWERED_BY} = ?
  AND {COL_QUESTION_ID} != ?
"""

#: Parameters: state, decline reason, reserved term (null unless the gate
#: declined on a reserved term), updated_at, id.
UPDATE_QUESTION_DECLINED: Final = f"""
UPDATE {TABLE_QUESTION_RECORDS}
SET {COL_QUESTION_STATE} = ?, {COL_QUESTION_DECLINE_REASON} = ?,
    {COL_QUESTION_RESERVED_TERM} = ?, {COL_QUESTION_UPDATED_AT} = ?
WHERE {COL_QUESTION_ID} = ?
"""

#: Parameters: state, answered_by, answer, updated_at, id.
UPDATE_QUESTION_ANSWERED: Final = f"""
UPDATE {TABLE_QUESTION_RECORDS}
SET {COL_QUESTION_STATE} = ?, {COL_QUESTION_ANSWERED_BY} = ?,
    {COL_QUESTION_ANSWER} = ?, {COL_QUESTION_UPDATED_AT} = ?
WHERE {COL_QUESTION_ID} = ?
"""

#: Parameters: blocked_state_id, updated_at, id.
UPDATE_QUESTION_BLOCK: Final = f"""
UPDATE {TABLE_QUESTION_RECORDS}
SET {COL_QUESTION_BLOCKED_STATE_ID} = ?, {COL_QUESTION_UPDATED_AT} = ?
WHERE {COL_QUESTION_ID} = ?
"""
