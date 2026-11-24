"""SQL for wakes (slice 244, D2, D3, D7, D10).

``LIVE_WAKE`` is the one liveness rule: the claim and every read use it, so a wake
whose wrapper was killed stops reading as running at its deadline everywhere at once.
Its parameter is ``now``; a row whose deadline is exactly ``now`` is no longer live.
"""

from __future__ import annotations

from typing import Final

#: A row not ended whose deadline is later than the parameter.
LIVE_WAKE: Final = "ended_at IS NULL AND deadline_at > ?"

#: Select order: ``store.wakes._wake`` reads these positionally.
_WAKE_COLUMNS: Final = (
    "wake_id, member_id, directory, command, started_at, deadline_at, log_stem, "
    "command_pid, ended_at, outcome, exit_code, detail, machine_id"
)
#: The columns the insert names itself: every ``_WAKE_COLUMNS`` one but the machine,
#: which follows the owner.
_INSERT_COLUMNS: Final = (
    "wake_id, member_id, directory, command, started_at, deadline_at, log_stem, "
    "command_pid, ended_at, outcome, exit_code, detail"
)

INSERT_WAKE: Final = (
    f"INSERT INTO wakes ({_INSERT_COLUMNS}, owner_id, machine_id) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
SELECT_WAKE: Final = f"SELECT {_WAKE_COLUMNS} FROM wakes WHERE wake_id = ?"
#: Every wake claimed for one machine, newest first. Parameter: machine id.
SELECT_WAKES_OF_MACHINE: Final = (
    f"SELECT {_WAKE_COLUMNS} FROM wakes WHERE machine_id = ? "
    "ORDER BY started_at DESC, wake_id"
)
#: Parameters: member id, now.
SELECT_LIVE_WAKE_EXISTS: Final = (
    f"SELECT EXISTS (SELECT 1 FROM wakes WHERE member_id = ? AND {LIVE_WAKE})"
)
#: Parameters: member id, the oldest ``started_at`` that still counts, exclusive.
COUNT_WAKES_SINCE: Final = (
    "SELECT COUNT(*) FROM wakes WHERE member_id = ? AND started_at > ?"
)
#: The member's unended row, newest first (a live one before an older overdue one),
#: with one more column: 1 when it is not live. Parameters: now, member id.
SELECT_UNENDED_WAKE: Final = (
    f"SELECT {_WAKE_COLUMNS}, NOT ({LIVE_WAKE}) FROM wakes "
    "WHERE member_id = ? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
)
SELECT_NEWEST_ENDED_WAKE: Final = (
    f"SELECT {_WAKE_COLUMNS} FROM wakes WHERE member_id = ? AND ended_at IS NOT NULL "
    "ORDER BY ended_at DESC, started_at DESC LIMIT 1"
)
#: Compare-and-set: only the first run of an unended wake records a pid.
SET_COMMAND_PID: Final = (
    "UPDATE wakes SET command_pid = ? "
    "WHERE wake_id = ? AND command_pid IS NULL AND ended_at IS NULL"
)
#: Compare-and-set: only a row that has not ended ends.
FINISH_WAKE: Final = (
    "UPDATE wakes SET ended_at = ?, outcome = ?, exit_code = ?, detail = ? "
    "WHERE wake_id = ? AND ended_at IS NULL"
)
#: Parameter: cutoff. Whatever the row's state.
DELETE_AGED_WAKES: Final = "DELETE FROM wakes WHERE started_at < ?"
SELECT_AGED_WAKE_EXISTS: Final = (
    "SELECT EXISTS (SELECT 1 FROM wakes WHERE started_at < ?)"
)

#: Each machine with a checkout of the member that has a wake command, with when it
#: last called the hub. Parameter: member id.
SELECT_WAKEABLE_MACHINES: Final = (
    "SELECT DISTINCT machines.name, machines.last_called_at FROM checkouts "
    "JOIN machines ON machines.machine_id = checkouts.machine_id "
    "WHERE checkouts.member_id = ? AND checkouts.wake_command IS NOT NULL "
    "ORDER BY machines.name"
)

# --- the wake mark (262 D8) ---------------------------------------------------

#: The newest mark among the member's open, unexpired requests; one null column when
#: there is none. Parameters: member id, the open state, now.
SELECT_NEWEST_WAKE_MARK: Final = (
    "SELECT MAX(wake_wanted_at) FROM messages "
    "WHERE to_member = ? AND kind = 'request' AND state = ? AND expires_at > ? "
    "AND wake_wanted_at IS NOT NULL"
)
#: Whether a wake of the member answers the mark: claimed at or after it, except a
#: claim nobody picked up (unended, no pid, past its deadline). A row with a pid is
#: its mark's wake whatever became of it. Parameters: member id, the mark, now.
SELECT_WAKE_FOR_MARK_EXISTS: Final = (
    "SELECT EXISTS (SELECT 1 FROM wakes WHERE member_id = ? AND started_at >= ? "
    "AND NOT (ended_at IS NULL AND command_pid IS NULL AND deadline_at <= ?))"
)
#: Sets the mark on one request that is still open. Parameters: now, message id, the
#: open state.
SET_WAKE_MARK: Final = (
    "UPDATE messages SET wake_wanted_at = ? WHERE message_id = ? AND state = ?"
)
