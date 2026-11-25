"""The machine entries ``status`` returns (slice 263, D11, D12).

Split from ``status_models`` to keep it under its size; ``status_models`` imports
``MachineEntry`` for ``StatusResult.machines``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from amoeba.operations.runs_document import RunCheckpoint


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MachineRunLine(_Model):
    """A run that is not completed, as another machine last reported it."""

    run_id: str
    pipeline: str
    #: Squadron's status text, raw.
    status: str
    directory: str | None
    #: Set when the run is paused and its listing gave a checkpoint.
    checkpoint: RunCheckpoint | None


class MachineEntry(_Model):
    """One machine: its last call, versions, and for another machine its runs."""

    name: str
    last_called_at: datetime | None
    client_version: str | None
    door_version: int | None
    #: True when the door version differs from the hub's, false when it is the same,
    #: null when none is recorded (the ``local`` machine).
    behind: bool | None
    #: True for the machine that made this call.
    calling: bool = False
    #: The calling machine's own runs are in ``status``'s other fields, not here:
    #: for it these are null and empty.
    runs_reported_at: datetime | None = None
    runs: tuple[MachineRunLine, ...] = ()
    #: Set when the stored document does not validate; then ``runs`` is empty.
    runs_problem: str | None = None
