"""SQL for serving sessions (slice 241, D6).

``LIVE_SESSION`` is the one stale rule: the prune, ``live_sessions`` and
``live_member_ids`` all use it, so a stale row is never shown whether or not it has
been pruned yet. Its parameter is the oldest heartbeat that still counts, ``now``
minus ``session_stale_seconds``; a row exactly that old is gone.
"""

from __future__ import annotations

from typing import Final

#: A row whose last heartbeat is newer than the parameter and that has a door version
#: (a row from before migration 014 has none and is never live).
LIVE_SESSION: Final = "heartbeat_at > ? AND door_version IS NOT NULL"
#: A session whose agent has answered a channel event.
PUSH_CONFIRMED: Final = "push_confirmed_at IS NOT NULL"
#: The waking rule: live, push confirmed, and on the door version the hub serves
#: (the bound parameter after the oldest heartbeat).
WAKING_SESSION: Final = f"{LIVE_SESSION} AND {PUSH_CONFIRMED} AND door_version = ?"

#: Select order: ``store.sessions._session`` reads these positionally.
_SESSION_COLUMNS: Final = (
    "session_id, member_id, client, directory, started_at, heartbeat_at, "
    "push_confirmed_at, client_version, door_version"
)

#: Register and beat in one statement: a first insert sets every column, a later
#: beat everything but ``started_at``, which stays the first.
#: The ``WHERE`` keeps another machine's session id from being refreshed:
#: no row is affected and ``upsert_session`` raises.
UPSERT_SESSION: Final = (
    f"INSERT INTO sessions ({_SESSION_COLUMNS}, owner_id, machine_id) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (session_id) DO UPDATE SET member_id = excluded.member_id, "
    "client = excluded.client, directory = excluded.directory, "
    "heartbeat_at = excluded.heartbeat_at, "
    "push_confirmed_at = excluded.push_confirmed_at, "
    "client_version = excluded.client_version, door_version = excluded.door_version "
    "WHERE sessions.machine_id = excluded.machine_id"
)
#: Only the calling machine's row: another machine's session id is left alone.
DELETE_SESSION: Final = "DELETE FROM sessions WHERE session_id = ? AND machine_id = ?"
SELECT_SESSION: Final = f"SELECT {_SESSION_COLUMNS} FROM sessions WHERE session_id = ?"
PRUNE_STALE_SESSIONS: Final = f"DELETE FROM sessions WHERE NOT ({LIVE_SESSION})"
SELECT_LIVE_SESSIONS: Final = (
    f"SELECT {_SESSION_COLUMNS} FROM sessions WHERE {LIVE_SESSION} "
    "ORDER BY started_at, session_id"
)
#: Each session's machine name, for the display (263 D12).
SELECT_SESSION_MACHINES: Final = (
    "SELECT sessions.session_id, machines.name FROM sessions "
    "JOIN machines ON machines.machine_id = sessions.machine_id"
)
SELECT_LIVE_MEMBER_IDS: Final = (
    f"SELECT DISTINCT member_id FROM sessions WHERE {WAKING_SESSION} ORDER BY member_id"
)
