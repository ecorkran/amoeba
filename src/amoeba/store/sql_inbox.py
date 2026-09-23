"""Every SQL statement and column name used by the inbox record and messages.

Sibling of ``sql.py`` and ``sql_journal.py``, under the same rule: a column name
or statement for ``inbox_submissions`` or ``messages`` appears here and in
migration ``004`` and nowhere else.

The one vocabulary value interpolated is ``Channel.INTENT``, into the
pending-intents query: SQLite only uses a partial index when the query repeats
the index's own ``WHERE`` literally, so the channel cannot travel as a bound
parameter there. It is a module constant, never caller data. Every other value
is a bound parameter.
"""

from __future__ import annotations

from typing import Final

from amoeba.store.inbox_models import Channel

# --------------------------------------------------------------------------
# Table names
# --------------------------------------------------------------------------

TABLE_INBOX_SUBMISSIONS: Final = "inbox_submissions"
TABLE_MESSAGES: Final = "messages"

# --------------------------------------------------------------------------
# inbox_submissions columns — the single definition site
# --------------------------------------------------------------------------

COL_SUBMISSION_APPLIED_SEQ: Final = "applied_seq"
COL_SUBMISSION_ID: Final = "id"
COL_SUBMISSION_PROJECT_ID: Final = "project_id"
COL_SUBMISSION_KIND: Final = "kind"
COL_SUBMISSION_SUBMITTED_BY: Final = "submitted_by"
COL_SUBMISSION_SUBMITTED_AT: Final = "submitted_at"
COL_SUBMISSION_PAYLOAD: Final = "payload"
COL_SUBMISSION_OUTCOME: Final = "outcome"
COL_SUBMISSION_REASON: Final = "reason"
COL_SUBMISSION_APPLIED_AT: Final = "applied_at"

#: Column order for every submission SELECT and for row mapping.
SUBMISSION_COLUMNS: Final = (
    COL_SUBMISSION_APPLIED_SEQ,
    COL_SUBMISSION_ID,
    COL_SUBMISSION_PROJECT_ID,
    COL_SUBMISSION_KIND,
    COL_SUBMISSION_SUBMITTED_BY,
    COL_SUBMISSION_SUBMITTED_AT,
    COL_SUBMISSION_PAYLOAD,
    COL_SUBMISSION_OUTCOME,
    COL_SUBMISSION_REASON,
    COL_SUBMISSION_APPLIED_AT,
)

# --------------------------------------------------------------------------
# messages columns — the single definition site
# --------------------------------------------------------------------------

COL_MESSAGE_SEQ: Final = "seq"
COL_MESSAGE_ID: Final = "id"
COL_MESSAGE_PROJECT_ID: Final = "project_id"
COL_MESSAGE_CHANNEL: Final = "channel"
COL_MESSAGE_NODE_ID: Final = "node_id"
COL_MESSAGE_BLOCKED_STATE_ID: Final = "blocked_state_id"
COL_MESSAGE_JOURNAL_ENTRY_ID: Final = "journal_entry_id"
COL_MESSAGE_SUBMISSION_ID: Final = "submission_id"
COL_MESSAGE_PAYLOAD: Final = "payload"
COL_MESSAGE_CREATED_AT: Final = "created_at"
COL_MESSAGE_ACKNOWLEDGED_AT: Final = "acknowledged_at"
COL_MESSAGE_ACKNOWLEDGED_BY: Final = "acknowledged_by"

#: Column order for every message SELECT and for row mapping.
MESSAGE_COLUMNS: Final = (
    COL_MESSAGE_SEQ,
    COL_MESSAGE_ID,
    COL_MESSAGE_PROJECT_ID,
    COL_MESSAGE_CHANNEL,
    COL_MESSAGE_NODE_ID,
    COL_MESSAGE_BLOCKED_STATE_ID,
    COL_MESSAGE_JOURNAL_ENTRY_ID,
    COL_MESSAGE_SUBMISSION_ID,
    COL_MESSAGE_PAYLOAD,
    COL_MESSAGE_CREATED_AT,
    COL_MESSAGE_ACKNOWLEDGED_AT,
    COL_MESSAGE_ACKNOWLEDGED_BY,
)

#: Index names, so the migration test asserts against constants.
INDEX_MESSAGES_PROJECT_CHANNEL_SEQ: Final = "idx_messages_project_channel_seq"
INDEX_MESSAGES_UNACKNOWLEDGED_INTENTS: Final = "idx_messages_unacknowledged_intents"

_SUBMISSION_SELECT_LIST: Final = ", ".join(SUBMISSION_COLUMNS)
_MESSAGE_SELECT_LIST: Final = ", ".join(MESSAGE_COLUMNS)

# --------------------------------------------------------------------------
# inbox_submissions statements
# --------------------------------------------------------------------------

#: Opens the apply transaction and takes the write lock **before** the replay
#: check. The connection's DEFERRED mode would otherwise begin only at the
#: first write, leaving the replay check and the precondition reads outside it.
BEGIN_IMMEDIATE: Final = "BEGIN IMMEDIATE"

#: ``applied_seq`` is omitted so SQLite assigns it — the receiver's order.
INSERT_SUBMISSION: Final = f"""
INSERT INTO {TABLE_INBOX_SUBMISSIONS} (
    {COL_SUBMISSION_ID},
    {COL_SUBMISSION_PROJECT_ID},
    {COL_SUBMISSION_KIND},
    {COL_SUBMISSION_SUBMITTED_BY},
    {COL_SUBMISSION_SUBMITTED_AT},
    {COL_SUBMISSION_PAYLOAD},
    {COL_SUBMISSION_OUTCOME},
    {COL_SUBMISSION_REASON},
    {COL_SUBMISSION_APPLIED_AT}
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_SUBMISSION_BY_ID: Final = f"""
SELECT {_SUBMISSION_SELECT_LIST}
FROM {TABLE_INBOX_SUBMISSIONS}
WHERE {COL_SUBMISSION_ID} = ?
"""

SELECT_SUBMISSIONS: Final = f"""
SELECT {_SUBMISSION_SELECT_LIST}
FROM {TABLE_INBOX_SUBMISSIONS}
WHERE {COL_SUBMISSION_PROJECT_ID} = ?
ORDER BY {COL_SUBMISSION_APPLIED_SEQ}
"""

SELECT_SUBMISSIONS_BY_OUTCOME: Final = f"""
SELECT {_SUBMISSION_SELECT_LIST}
FROM {TABLE_INBOX_SUBMISSIONS}
WHERE {COL_SUBMISSION_PROJECT_ID} = ?
  AND {COL_SUBMISSION_OUTCOME} = ?
ORDER BY {COL_SUBMISSION_APPLIED_SEQ}
"""

# --------------------------------------------------------------------------
# messages statements
# --------------------------------------------------------------------------

#: ``seq`` is omitted so SQLite assigns it — the replay cursor.
INSERT_MESSAGE: Final = f"""
INSERT INTO {TABLE_MESSAGES} (
    {COL_MESSAGE_ID},
    {COL_MESSAGE_PROJECT_ID},
    {COL_MESSAGE_CHANNEL},
    {COL_MESSAGE_NODE_ID},
    {COL_MESSAGE_BLOCKED_STATE_ID},
    {COL_MESSAGE_JOURNAL_ENTRY_ID},
    {COL_MESSAGE_SUBMISSION_ID},
    {COL_MESSAGE_PAYLOAD},
    {COL_MESSAGE_CREATED_AT}
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_MESSAGE_BY_ID: Final = f"""
SELECT {_MESSAGE_SELECT_LIST}
FROM {TABLE_MESSAGES}
WHERE {COL_MESSAGE_ID} = ?
"""

#: The replay primitive. Served by the (project, channel, seq) index.
SELECT_MESSAGES_AFTER: Final = f"""
SELECT {_MESSAGE_SELECT_LIST}
FROM {TABLE_MESSAGES}
WHERE {COL_MESSAGE_PROJECT_ID} = ?
  AND {COL_MESSAGE_CHANNEL} = ?
  AND {COL_MESSAGE_SEQ} > ?
ORDER BY {COL_MESSAGE_SEQ}
"""

#: What the Runner consumes. Repeats the partial index's WHERE exactly.
SELECT_PENDING_INTENTS: Final = f"""
SELECT {_MESSAGE_SELECT_LIST}
FROM {TABLE_MESSAGES}
WHERE {COL_MESSAGE_PROJECT_ID} = ?
  AND {COL_MESSAGE_CHANNEL} = '{Channel.INTENT.value}'
  AND {COL_MESSAGE_ACKNOWLEDGED_AT} IS NULL
ORDER BY {COL_MESSAGE_SEQ}
"""

#: Marks an intent consumed. The channel and ``IS NULL`` guards make an
#: already-acknowledged or non-intent row a zero-rowcount result, so the caller
#: raises instead of overwriting.
ACKNOWLEDGE_MESSAGE: Final = f"""
UPDATE {TABLE_MESSAGES}
SET {COL_MESSAGE_ACKNOWLEDGED_AT} = ?,
    {COL_MESSAGE_ACKNOWLEDGED_BY} = ?
WHERE {COL_MESSAGE_ID} = ?
  AND {COL_MESSAGE_CHANNEL} = ?
  AND {COL_MESSAGE_ACKNOWLEDGED_AT} IS NULL
"""
