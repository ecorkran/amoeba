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

#: Parameters: state, decline reason, updated_at, id.
UPDATE_QUESTION_DECLINED: Final = f"""
UPDATE {TABLE_QUESTION_RECORDS}
SET {COL_QUESTION_STATE} = ?, {COL_QUESTION_DECLINE_REASON} = ?,
    {COL_QUESTION_UPDATED_AT} = ?
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
