"""The ``runs`` document each machine last reported (slice 263, D11).

One row per machine, replaced by each ``status`` or ``list`` call of that machine and
shown by the others with when it was reported. The store holds the document as the
text it was given; the operation that reads it validates it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from amoeba.store import sql_machine_runs
from amoeba.store.row_values import decode_timestamp, encode_timestamp, integer, text
from amoeba.store.store import Transaction


@dataclass(frozen=True)
class MachineRuns:
    """One machine's stored report."""

    machine_id: int
    machine: str
    reported_at: datetime
    document: str


def put_machine_runs(transaction: Transaction, document: str, now: datetime) -> None:
    """Store ``document`` as the acting machine's report, replacing its last one."""
    acting = transaction.acting("machine_runs")
    transaction.execute(
        sql_machine_runs.PUT_MACHINE_RUNS,
        (acting.machine_id, acting.owner_id, encode_timestamp(now), document),
    )


def get_machine_runs(transaction: Transaction, machine_id: int) -> MachineRuns | None:
    """The machine's stored report, or ``None`` when it has stored none."""
    row = transaction.execute(
        sql_machine_runs.SELECT_MACHINE_RUNS, (machine_id,)
    ).fetchone()
    return None if row is None else _runs(tuple(row))


def all_machine_runs(transaction: Transaction) -> tuple[MachineRuns, ...]:
    """Every stored report, by machine name."""
    rows = transaction.execute(sql_machine_runs.SELECT_ALL_MACHINE_RUNS).fetchall()
    return tuple(_runs(tuple(row)) for row in rows)


def delete_machine_runs(transaction: Transaction, machine_id: int) -> None:
    """Remove the machine's report; none stored is a no-op."""
    transaction.execute(sql_machine_runs.DELETE_MACHINE_RUNS_BY_ID, (machine_id,))


def _runs(row: tuple[object, ...]) -> MachineRuns:
    return MachineRuns(
        machine_id=integer(row[0], "machine_runs.machine_id"),
        machine=text(row[1], "machines.name"),
        reported_at=decode_timestamp(row[2], "machine_runs.reported_at"),
        document=text(row[3], "machine_runs.document"),
    )
