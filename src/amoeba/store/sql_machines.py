"""SQL for owners, machines, kept results and the closed mark (slice 260, D12).

Values always bind with ``?``; nothing here is built from a runtime value.
"""

from __future__ import annotations

from typing import Final

SELECT_OWNER_IDS: Final = "SELECT owner_id FROM owners ORDER BY owner_id"
SELECT_MACHINE_BY_NAME: Final = (
    "SELECT machine_id, owner_id FROM machines WHERE name = ?"
)
INSERT_MACHINE_NO_TOKEN: Final = (
    "INSERT INTO machines (name, owner_id, token_hash, created_at) "
    "VALUES (?, ?, NULL, ?)"
)
SELECT_CLOSED_MARK: Final = "SELECT hub_address, closed_at FROM closed_mark"
# Parameters: hub address, time. The one row has the fixed key 1 (D12).
REPLACE_CLOSED_MARK: Final = (
    "INSERT OR REPLACE INTO closed_mark (mark_key, hub_address, closed_at) "
    "VALUES (1, ?, ?)"
)
DELETE_CLOSED_MARK: Final = "DELETE FROM closed_mark"

# --- machines with a token (slice 260, D3, D8, D13) -----------------------------

SELECT_MACHINE_BY_TOKEN: Final = (
    "SELECT machine_id, owner_id FROM machines WHERE token_hash = ?"
)
# Parameters: token hash, name.
SET_TOKEN_HASH: Final = "UPDATE machines SET token_hash = ? WHERE name = ?"
INSERT_MACHINE: Final = (
    "INSERT INTO machines (name, owner_id, token_hash, created_at) VALUES (?, ?, ?, ?)"
)
# Parameters: time, client version, door version, token hash. A null version leaves
# the stored one as it was.
TOUCH_MACHINE: Final = (
    "UPDATE machines SET last_called_at = ?, "
    "client_version = COALESCE(?, client_version), "
    "door_version = COALESCE(?, door_version) WHERE token_hash = ?"
)
# Parameters: time, token hash. A session's tick or exit call (263 D6).
TOUCH_MACHINE_TIME_ONLY: Final = (
    "UPDATE machines SET last_called_at = ? WHERE token_hash = ?"
)
SELECT_MACHINES_CALLED: Final = (
    "SELECT machine_id, name, last_called_at FROM machines ORDER BY machine_id"
)
SELECT_MACHINE_NAME: Final = "SELECT name FROM machines WHERE machine_id = ?"
SELECT_MACHINES: Final = (
    "SELECT name, token_hash IS NOT NULL, last_called_at, client_version, "
    "door_version "
    "FROM machines ORDER BY name"
)
DELETE_MACHINE_SESSIONS: Final = (
    "DELETE FROM sessions WHERE machine_id = (SELECT machine_id FROM machines "
    "WHERE name = ?)"
)
DELETE_MACHINE_RESULTS: Final = (
    "DELETE FROM call_results WHERE machine_id = (SELECT machine_id FROM machines "
    "WHERE name = ?)"
)
DELETE_MACHINE: Final = "DELETE FROM machines WHERE name = ?"
DELETE_MACHINE_RUNS: Final = (
    "DELETE FROM machine_runs WHERE machine_id = (SELECT machine_id FROM machines "
    "WHERE name = ?)"
)
