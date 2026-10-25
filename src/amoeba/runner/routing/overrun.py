"""Runs past their pipeline's time bound (D7).

The table sets each pipeline's bound; the response is fixed. An in-flight run has
no outcome to route, so an overrun is a project-scoped ``run_overrun`` escalation
and never a decision record (the entry's one decision belongs to its eventual
outcome). The run is never killed: it is observed and ingested as usual.

``overrun_runs`` is pure. ``watch_overruns`` adds the fault to a tick's faults, as
``pointer_watch`` does for a moved pointer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from amoeba.runner.dispatch.pointer_watch import (
    LISTING_NODE_ID,
    LISTING_RUN_ID,
    PAYLOAD_RUNS,
)
from amoeba.runner.faults import Fault, FaultKind, TickFaults
from amoeba.runner.ingest.record import entry_run_id
from amoeba.runner.launch import PARAM_PIPELINE
from amoeba.runner.routing.engine import PAYLOAD_TABLE_VERSION
from amoeba.runner.routing.table import RoutingTable
from amoeba.store import JournalEntry

#: Keys of each overrunning-run listing in the escalation payload.
LISTING_PIPELINE = "pipeline"
LISTING_ISSUED_AT = "issued_at"
LISTING_BOUND_MINUTES = "bound_minutes"


@dataclass(frozen=True)
class Overrun:
    """A run in flight longer than its pipeline's bound."""

    node_id: str
    run_id: str
    pipeline: str
    issued_at: datetime
    bound_minutes: int


def overrun_runs(
    in_flight: Sequence[JournalEntry], table: RoutingTable, now: datetime
) -> tuple[Overrun, ...]:
    """The in-flight entries older than their pipeline's bound, in the given order.

    Age is ``now - issued_at``; a run exactly at its bound has not overrun.

    Raises:
        ValueError: An entry names a pipeline the table has no bound for, or has
            no pipeline, or has no timezone-aware ``issued_at``. Load validation
            bounds every pipeline the Runner launches, so these are programming
            errors, and the project is faulted through 122's catch.
    """
    found: list[Overrun] = []
    for entry in in_flight:
        pipeline = entry.parameters.get(PARAM_PIPELINE)
        if not isinstance(pipeline, str):
            raise ValueError(f"entry {entry.id} carries no pipeline: {pipeline!r}")
        bound = table.time_bounds_minutes.get(pipeline)
        if bound is None:
            raise ValueError(
                f"entry {entry.id} runs pipeline {pipeline}, which table "
                f"{table.version} has no time bound for"
            )
        issued_at = entry.issued_at
        if issued_at is None or issued_at.tzinfo is None:
            raise ValueError(f"entry {entry.id} has no timezone-aware issued_at")
        if now - issued_at > timedelta(minutes=bound):
            found.append(
                Overrun(entry.node_id, entry_run_id(entry), pipeline, issued_at, bound)
            )
    return tuple(found)


def watch_overruns(
    in_flight: Sequence[JournalEntry],
    table: RoutingTable,
    now: datetime,
    faults: TickFaults,
) -> None:
    """Add a ``run_overrun`` fault to ``faults`` while any run exceeds its bound.

    The fault recurs on every tick the condition holds, so the escalation stays
    open, and it closes on the first complete tick without it (122's closure rule).
    """
    overruns = overrun_runs(in_flight, table, now)
    if not overruns:
        return
    listing = [
        {
            LISTING_NODE_ID: overrun.node_id,
            LISTING_RUN_ID: overrun.run_id,
            LISTING_PIPELINE: overrun.pipeline,
            LISTING_ISSUED_AT: overrun.issued_at.isoformat(),
            LISTING_BOUND_MINUTES: overrun.bound_minutes,
        }
        for overrun in overruns
    ]
    faults.add(
        Fault(
            FaultKind.RUN_OVERRUN,
            f"{len(overruns)} run(s) in flight have outlived their pipeline's "
            "time bound",
            extra={PAYLOAD_RUNS: listing, PAYLOAD_TABLE_VERSION: table.version},
        )
    )
