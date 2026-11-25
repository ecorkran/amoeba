"""The machines ``status`` and ``list`` show, and the runs each last reported
(slice 263, D11, D12).

The hub part stores the calling machine's ``runs`` document, then reads every other
machine's: it is shown as that machine last reported it, never placed under members and
never used to close or sweep anything.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import ValidationError

from amoeba.operations.reject_codes import validation_problems
from amoeba.operations.runs_document import RunsDocument
from amoeba.operations.status_machine_models import MachineEntry, MachineRunLine
from amoeba.store.errors import StoreBusyError
from amoeba.store.machine_runs import MachineRuns, all_machine_runs, put_machine_runs
from amoeba.store.machines import (
    MachineRow,
    acting_machine_name,
    list_machines,
)
from amoeba.store.store import Store


def differs_from_hub(door_version: int, hub_door_version: int) -> bool:
    """The one statement of "behind": a door version other than the hub's (a session
    on another version cannot take a wake, D6). ``sql_sessions.WAKING_SESSION`` is the
    same rule in SQL."""
    return door_version != hub_door_version


def is_behind(door_version: int | None, hub_door_version: int) -> bool | None:
    """``differs_from_hub``, or ``None`` when no door version is recorded."""
    if door_version is None:
        return None
    return differs_from_hub(door_version, hub_door_version)


def store_calling_runs(store: Store, runs: RunsDocument, now: datetime) -> str | None:
    """Keep the calling machine's document as its last report, in the call's
    transaction (a savepoint on a hub): a failed write fails the call.

    A store busy past its wait is the one exception, as for the sweeps: it returns a
    problem text, and the call goes on without storing the report.
    """
    try:
        with store.write() as transaction:
            put_machine_runs(transaction, runs.model_dump_json(), now)
    except StoreBusyError as error:
        return f"the runs report was not stored: {error}"
    return None


def read_machines(store: Store, hub_door_version: int) -> tuple[MachineEntry, ...]:
    """The calling machine and every machine with a token, by name; each other machine
    with the run lines it last reported, or why they cannot be read."""
    with store.read() as transaction:
        calling = acting_machine_name(transaction)
        rows = list_machines(transaction)
        reports = {item.machine: item for item in all_machine_runs(transaction)}
    return tuple(
        _entry(row, hub_door_version, None if row.name == calling else reports)
        for row in rows
        if row.has_token or row.name == calling
    )


def _entry(
    row: MachineRow, hub_door_version: int, reports: dict[str, MachineRuns] | None
) -> MachineEntry:
    entry = MachineEntry(
        name=row.name,
        last_called_at=row.last_called_at,
        client_version=row.client_version,
        door_version=row.door_version,
        behind=is_behind(row.door_version, hub_door_version),
        calling=reports is None,
    )
    report = None if reports is None else reports.get(row.name)
    if report is None:
        return entry
    entry = entry.model_copy(update={"runs_reported_at": report.reported_at})
    try:
        document = RunsDocument.model_validate_json(report.document)
    except ValidationError as error:
        problem = "; ".join(validation_problems(error))
        return entry.model_copy(update={"runs_problem": problem})
    lines = tuple(
        MachineRunLine(
            run_id=run.run_id,
            pipeline=run.pipeline,
            status=run.status,
            directory=run.working_directory,
            checkpoint=run.checkpoint,
        )
        for run in document.open_runs
    )
    return entry.model_copy(update={"runs": lines})
