"""SQL for kept call results (slice 260, D9)."""

from __future__ import annotations

from typing import Final

# Parameters: machine id, call id.
SELECT_KEPT: Final = (
    "SELECT operation, request_hash, reply FROM call_results "
    "WHERE machine_id = ? AND call_id = ?"
)
INSERT_KEPT: Final = (
    "INSERT INTO call_results "
    "(machine_id, call_id, operation, request_hash, reply, recorded_at) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)
# Parameter: the oldest ``recorded_at`` that is kept (older rows go).
DELETE_EXPIRED: Final = "DELETE FROM call_results WHERE recorded_at < ?"
