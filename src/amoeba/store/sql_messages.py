"""SQL for requests, deliveries and rejections (slice 240).

Kept apart from ``sql.py``, which is past its size guide. Nothing here names the
``members`` table: a member check goes through ``sql.SELECT_MEMBER``, so "a removed
member is not a member" stays written once, as ``sql.ACTIVE_MEMBER``.
"""

from __future__ import annotations

from typing import Final

from amoeba.store.vocabulary import MessageKind, RequestState

#: Select order: ``store.messages._message`` reads these positionally.
_MESSAGE_COLUMNS: Final = (
    "message_id, kind, from_member, to_member, to_program, parent_id, depth, "
    "subject, body, state, result, result_commit, result_version, reason, "
    "accepted_at, created_at, state_changed_at, expires_at"
)

#: How many columns a ``messages`` select returns, for splitting a joined row.
MESSAGE_COLUMN_COUNT: Final = len(_MESSAGE_COLUMNS.split(","))

#: A new request: ``state_changed_at`` is its creation time, ``state`` is ``open``.
INSERT_REQUEST: Final = (
    "INSERT INTO messages (message_id, kind, from_member, to_member, parent_id, "
    "depth, subject, body, state, created_at, state_changed_at, expires_at, "
    "owner_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
SELECT_MESSAGE: Final = f"SELECT {_MESSAGE_COLUMNS} FROM messages WHERE message_id = ?"


def _quoted(values: frozenset[RequestState]) -> str:
    """``'a', 'b'`` for an ``IN`` list, in a fixed order."""
    return ", ".join(f"'{value.value}'" for value in sorted(values))


#: The requests' states a request never leaves; the one place the SQL spells them.
_TERMINAL: Final = _quoted(RequestState.terminal())
#: A request that can still change. A note has no state and never matches.
LIVE_REQUEST: Final = f"kind = 'request' AND state NOT IN ({_TERMINAL})"
#: A request old enough to prune; keyed on the terminal states, so a note never matches.
PRUNABLE_REQUEST: Final = (
    f"kind = 'request' AND state IN ({_TERMINAL}) AND state_changed_at < ?"
)

#: A note, and a note old enough to prune (243 D6). Notes have no state, so the prune
#: keys on ``created_at``. The one place the SQL spells the kind for notes. ``state IS
#: NULL`` is true of every note (the table's ``CHECK``) and no request, and lets the
#: due check search ``messages_state_expires`` instead of scanning the table.
_NOTE: Final = f"kind = '{MessageKind.NOTE.value}'"
PRUNABLE_NOTE: Final = f"{_NOTE} AND state IS NULL AND created_at < ?"

# --- notes (slice 243) -----------------------------------------------------

#: A new note: no state and no expiry; ``state_changed_at`` is its creation time.
INSERT_NOTE: Final = (
    "INSERT INTO messages (message_id, kind, from_member, to_member, to_program, "
    "depth, subject, body, created_at, state_changed_at, owner_id) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_DELIVERY_COLUMNS: Final = (
    "delivery.seq, delivery.member_id, delivery.message_id, delivery.event, "
    "delivery.created_at"
)
_QUALIFIED_MESSAGE_COLUMNS: Final = ", ".join(
    f"message.{column.strip()}" for column in _MESSAGE_COLUMNS.split(",")
)
#: The notes a member has a ``sent`` delivery for after ``seq``, each with that
#: delivery: message columns, then delivery columns. Parameters: member, seq.
SELECT_RECEIVED_NOTES: Final = (
    f"SELECT {_QUALIFIED_MESSAGE_COLUMNS}, {_DELIVERY_COLUMNS} "
    "FROM deliveries AS delivery "
    "JOIN messages AS message ON message.message_id = delivery.message_id "
    f"WHERE message.{_NOTE} AND delivery.member_id = ? AND delivery.seq > ? "
    "ORDER BY delivery.seq"
)
DELETE_PRUNABLE_NOTE_DELIVERIES: Final = (
    "DELETE FROM deliveries WHERE message_id IN "
    f"(SELECT message_id FROM messages WHERE {PRUNABLE_NOTE})"
)
DELETE_PRUNABLE_NOTES: Final = f"DELETE FROM messages WHERE {PRUNABLE_NOTE}"
#: A sender's notes beyond its newest ones, as ids. Parameters: member, how many to
#: keep (``LIMIT -1`` is SQLite's no limit, so the offset alone skips the kept ones).
SELECT_NOTES_BEYOND_NEWEST_FROM: Final = (
    f"SELECT message_id FROM messages WHERE {_NOTE} AND from_member = ? "
    "ORDER BY created_at DESC, message_id DESC LIMIT -1 OFFSET ?"
)

# --- state changes ---------------------------------------------------------

#: A null parameter keeps the stored value, so each change names only what it sets.
UPDATE_STATE: Final = (
    "UPDATE messages SET state = ?, result = COALESCE(?, result), "
    "result_commit = COALESCE(?, result_commit), "
    "result_version = COALESCE(?, result_version), reason = COALESCE(?, reason), "
    "accepted_at = COALESCE(?, accepted_at), state_changed_at = ? "
    "WHERE message_id = ?"
)
SELECT_LIVE_REQUESTS_OF: Final = (
    f"SELECT {_MESSAGE_COLUMNS} FROM messages "
    f"WHERE {LIVE_REQUEST} AND (from_member = ? OR to_member = ?) "
    "ORDER BY created_at, message_id"
)

#: The live children of every live request the member sent or received, as
#: ``(parent_id, child_id)`` pairs: the chain's next links, in one read.
SELECT_LIVE_CHILDREN_OF_MEMBER: Final = (
    "SELECT child.parent_id, child.message_id FROM messages AS child "
    "JOIN messages AS parent ON child.parent_id = parent.message_id "
    f"WHERE child.kind = 'request' AND child.state NOT IN ({_TERMINAL}) "
    f"AND parent.kind = 'request' AND parent.state NOT IN ({_TERMINAL}) "
    "AND (parent.from_member = ? OR parent.to_member = ?) "
    "ORDER BY child.created_at, child.message_id"
)
#: Every request the member sent or received that is still held, oldest first.
SELECT_REQUESTS_OF: Final = (
    f"SELECT {_MESSAGE_COLUMNS} FROM messages "
    "WHERE kind = 'request' AND (from_member = ? OR to_member = ?) "
    "ORDER BY created_at, message_id"
)
#: The requests a member's deliveries after ``since`` concern, and the member's open
#: requests already past ``expires_at`` that the sweep has not yet recorded.
SELECT_REQUESTS_CHANGED_SINCE: Final = (
    f"SELECT {_MESSAGE_COLUMNS} FROM messages WHERE kind = 'request' AND ("
    "message_id IN (SELECT message_id FROM deliveries WHERE member_id = ? AND seq > ?) "
    f"OR (state = '{RequestState.OPEN.value}' AND expires_at <= ? "
    "AND (from_member = ? OR to_member = ?))) "
    "ORDER BY created_at, message_id"
)

# --- deliveries ------------------------------------------------------------

INSERT_DELIVERY: Final = (
    "INSERT INTO deliveries (member_id, message_id, event, created_at, owner_id) "
    "VALUES (?, ?, ?, ?, ?)"
)
#: Select order: ``store.deliveries.delivery_from_row`` reads these positionally.
SELECT_DELIVERIES_SINCE: Final = (
    "SELECT seq, member_id, message_id, event, created_at FROM deliveries "
    "WHERE member_id = ? AND seq > ? ORDER BY seq"
)
#: ``sqlite_sequence`` keeps the highest ``seq`` ever assigned, so it does not fall
#: when the prune deletes delivery rows. No row means none was ever assigned.
SELECT_HIGHEST_ASSIGNED_SEQ: Final = (
    "SELECT seq FROM sqlite_sequence WHERE name = 'deliveries'"
)

# --- push reads (slice 241, D2, D4) ----------------------------------------

#: The push check: one indexed read on ``(member_id, seq)``; null with no rows.
SELECT_MEMBER_HIGH_SEQ: Final = "SELECT MAX(seq) FROM deliveries WHERE member_id = ?"
#: The member's deliveries above a number, each with its message's kind and the
#: counterparty: a note's sender, else the request member that is not the receiver.
SELECT_PUSH_ROWS_AFTER: Final = (
    "SELECT delivery.seq, delivery.event, message.kind, "
    f"CASE WHEN message.kind = '{MessageKind.NOTE.value}' "
    "OR message.to_member = delivery.member_id "
    "THEN message.from_member ELSE message.to_member END "
    "FROM deliveries AS delivery "
    "JOIN messages AS message ON message.message_id = delivery.message_id "
    "WHERE delivery.member_id = ? AND delivery.seq > ? ORDER BY delivery.seq"
)

# --- sweep -----------------------------------------------------------------

SELECT_DUE_REQUESTS: Final = (
    f"SELECT {_MESSAGE_COLUMNS} FROM messages "
    f"WHERE kind = 'request' AND state = '{RequestState.OPEN.value}' "
    "AND expires_at <= ? ORDER BY expires_at, message_id"
)
DELETE_PRUNABLE_DELIVERIES: Final = (
    "DELETE FROM deliveries WHERE message_id IN "
    f"(SELECT message_id FROM messages WHERE {PRUNABLE_REQUEST})"
)
DELETE_PRUNABLE_REQUESTS: Final = f"DELETE FROM messages WHERE {PRUNABLE_REQUEST}"
DELETE_OLD_REJECTIONS: Final = "DELETE FROM message_rejections WHERE created_at < ?"
#: Keeps a member's newest rows. Parameters: member, member, rows to keep.
TRIM_REJECTIONS: Final = (
    "DELETE FROM message_rejections WHERE member_id = ? AND id NOT IN "
    "(SELECT id FROM message_rejections WHERE member_id = ? ORDER BY id DESC LIMIT ?)"
)
#: ``(requests the member sent, of them how many can still change)``.
COUNT_REQUESTS_FROM: Final = (
    "SELECT count(*), COALESCE(SUM(CASE WHEN state NOT IN "
    f"({_TERMINAL}) THEN 1 ELSE 0 END), 0) "
    "FROM messages WHERE kind = 'request' AND from_member = ?"
)
#: The member's finished requests, oldest first. Parameters: member, how many.
SELECT_OLDEST_TERMINAL_FROM: Final = (
    "SELECT message_id FROM messages WHERE kind = 'request' AND from_member = ? "
    f"AND state IN ({_TERMINAL}) ORDER BY state_changed_at, message_id LIMIT ?"
)
DELETE_DELIVERIES_OF: Final = "DELETE FROM deliveries WHERE message_id = ?"
DELETE_MESSAGE: Final = "DELETE FROM messages WHERE message_id = ?"
#: Parameters: now, request cutoff, note cutoff, rejection cutoff. Answers "is
#: anything due".
SELECT_SWEEP_DUE: Final = (
    "SELECT EXISTS (SELECT 1 FROM messages WHERE kind = 'request' "
    f"AND state = '{RequestState.OPEN.value}' AND expires_at <= ?) "
    f"OR EXISTS (SELECT 1 FROM messages WHERE {PRUNABLE_REQUEST}) "
    f"OR EXISTS (SELECT 1 FROM messages WHERE {PRUNABLE_NOTE}) "
    "OR EXISTS (SELECT 1 FROM message_rejections WHERE created_at < ?)"
)

# --- rejections ------------------------------------------------------------

INSERT_REJECTION: Final = (
    "INSERT INTO message_rejections (member_id, operation, to_ref, message_id, "
    "parent_id, code, detail, created_at, owner_id) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
#: The member's retained rejections, newest first.
SELECT_REJECTIONS_OF: Final = (
    "SELECT id, member_id, operation, to_ref, message_id, parent_id, code, detail, "
    "created_at FROM message_rejections WHERE member_id = ? ORDER BY id DESC"
)
