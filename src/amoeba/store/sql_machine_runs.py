"""SQL for ``machine_runs`` (slice 263, D11). Values bind with ``?``."""

from __future__ import annotations

from typing import Final

# Parameters: machine id, owner id, reported_at, document, reported_at, document.
PUT_MACHINE_RUNS: Final = (
    "INSERT INTO machine_runs (machine_id, owner_id, reported_at, document) "
    "VALUES (?, ?, ?, ?) ON CONFLICT (machine_id) DO UPDATE SET "
    "reported_at = excluded.reported_at, document = excluded.document"
)
_SELECT: Final = (
    "SELECT machine_runs.machine_id, machines.name, machine_runs.reported_at, "
    "machine_runs.document FROM machine_runs "
    "JOIN machines ON machines.machine_id = machine_runs.machine_id"
)
SELECT_MACHINE_RUNS: Final = f"{_SELECT} WHERE machine_runs.machine_id = ?"
SELECT_ALL_MACHINE_RUNS: Final = f"{_SELECT} ORDER BY machines.name"
DELETE_MACHINE_RUNS_BY_ID: Final = "DELETE FROM machine_runs WHERE machine_id = ?"
