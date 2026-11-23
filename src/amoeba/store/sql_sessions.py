"""SQL for serving sessions (slice 241, D6).

``LIVE_SESSION`` is the one stale rule: the prune, ``live_sessions`` and
``live_member_ids`` all use it, so a stale row is never shown whether or not it has
been pruned yet. Its parameter is the oldest heartbeat that still counts, ``now``
minus ``session_stale_seconds``; a row exactly that old is gone.
"""

from __future__ import annotations

from typing import Final

#: A row whose last heartbeat is newer than the parameter.
LIVE_SESSION: Final = "heartbeat_at > ?"
#: A session whose agent has answered a channel event.
PUSH_CONFIRMED: Final = "push_confirmed_at IS NOT NULL"

#: Select order: ``store.sessions._session`` reads these positionally.
_SESSION_COLUMNS: Final = (
    "session_id, member_id, client, directory, started_at, heartbeat_at, "
    "push_confirmed_at"
)

#: Register and beat in one statement: a first insert sets every column, a later
#: beat only the heartbeat and the confirmation, so ``started_at`` stays the first.
UPSERT_SESSION: Final = (
    f"INSERT INTO sessions ({_SESSION_COLUMNS}, owner_id, machine_id) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (session_id) DO UPDATE SET heartbeat_at = excluded.heartbeat_at, "
    "push_confirmed_at = excluded.push_confirmed_at"
)
DELETE_SESSION: Final = "DELETE FROM sessions WHERE session_id = ?"
PRUNE_STALE_SESSIONS: Final = f"DELETE FROM sessions WHERE NOT ({LIVE_SESSION})"
SELECT_LIVE_SESSIONS: Final = (
    f"SELECT {_SESSION_COLUMNS} FROM sessions WHERE {LIVE_SESSION} "
    "ORDER BY started_at, session_id"
)
SELECT_LIVE_MEMBER_IDS: Final = (
    f"SELECT DISTINCT member_id FROM sessions "
    f"WHERE {LIVE_SESSION} AND {PUSH_CONFIRMED} ORDER BY member_id"
)
