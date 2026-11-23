"""SQL for checkouts (slice 261, D2, D7, D8).

Values always bind with ``?``; nothing here is built from a runtime value. No
statement here names ``members``: that table's statements are all in ``sql.py``.
"""

from __future__ import annotations

from typing import Final

_COLUMNS: Final = (
    "checkout_id, member_id, machine_id, cf_project_id, path, wake_command, "
    "added_at, updated_at"
)
#: Oldest first, so "the one added first" (D9, D11, D13) is the first row.
_ADDED_ORDER: Final = "ORDER BY added_at, checkout_id"

# Parameters: member, machine, Context Forge id, path, wake command, owner, then the
# two times.
INSERT_CHECKOUT: Final = (
    "INSERT INTO checkouts (member_id, machine_id, cf_project_id, path, "
    "wake_command, owner_id, added_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)
SELECT_CHECKOUT_AT: Final = (
    f"SELECT {_COLUMNS} FROM checkouts WHERE machine_id = ? AND cf_project_id = ?"
)
SELECT_CHECKOUTS_OF_MEMBER: Final = (
    f"SELECT {_COLUMNS} FROM checkouts WHERE member_id = ? {_ADDED_ORDER}"
)
SELECT_CHECKOUTS_ON_MACHINE: Final = (
    f"SELECT {_COLUMNS} FROM checkouts WHERE machine_id = ? {_ADDED_ORDER}"
)
SELECT_FIRST_CHECKOUT_ON: Final = (
    f"SELECT {_COLUMNS} FROM checkouts WHERE member_id = ? AND machine_id = ? "
    f"{_ADDED_ORDER} LIMIT 1"
)
DELETE_CHECKOUT: Final = "DELETE FROM checkouts WHERE checkout_id = ?"
DELETE_CHECKOUTS_OF_MEMBER: Final = "DELETE FROM checkouts WHERE member_id = ?"
DELETE_CHECKOUTS_ON_MACHINE: Final = "DELETE FROM checkouts WHERE machine_id = ?"
# Parameters: machine, path with trailing slashes dropped. The stored side drops them
# too; ``RTRIM`` removes every trailing slash and keeps a lone "/" as "".
DELETE_CHECKOUTS_AT_PATH: Final = (
    "DELETE FROM checkouts WHERE machine_id = ? AND RTRIM(path, '/') = ?"
)
# Parameters: command (or null), time, checkout id.
SET_CHECKOUT_WAKE_COMMAND: Final = (
    "UPDATE checkouts SET wake_command = ?, updated_at = ? WHERE checkout_id = ?"
)
SELECT_CHECKOUT_MACHINE: Final = (
    "SELECT checkouts.machine_id, machines.name FROM checkouts "
    "JOIN machines ON machines.machine_id = checkouts.machine_id "
    "WHERE checkouts.checkout_id = ?"
)
SELECT_MACHINE_NAME: Final = "SELECT name FROM machines WHERE machine_id = ?"

# The first-added checkout with a wake command (D9): one machine's, or any machine's.
SELECT_WAKEABLE_CHECKOUT_ON: Final = (
    f"SELECT {_COLUMNS} FROM checkouts WHERE member_id = ? AND machine_id = ? "
    f"AND wake_command IS NOT NULL {_ADDED_ORDER} LIMIT 1"
)
SELECT_WAKEABLE_CHECKOUT_ANYWHERE: Final = (
    f"SELECT {_COLUMNS} FROM checkouts WHERE member_id = ? "
    f"AND wake_command IS NOT NULL {_ADDED_ORDER} LIMIT 1"
)

# A member's checkouts with the name of each one's machine, oldest first (D13).
SELECT_CHECKOUT_LISTING: Final = (
    "SELECT checkouts.checkout_id, checkouts.member_id, checkouts.machine_id, "
    "checkouts.cf_project_id, checkouts.path, checkouts.wake_command, "
    "checkouts.added_at, checkouts.updated_at, machines.name FROM checkouts "
    "JOIN machines ON machines.machine_id = checkouts.machine_id "
    "WHERE checkouts.member_id = ? ORDER BY checkouts.added_at, checkouts.checkout_id"
)
