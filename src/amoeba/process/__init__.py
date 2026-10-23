"""The Amoeba resident process: host loop, recovery, and the observers.

One long-lived process per supervisor owns the stores read-write, hosts
*tenants* (the inbox apply loop in slice 103, the Runner in initiative 120),
and reconciles every journaled-but-unresolved command on start.

The full contract is documented in ``docs/process-contract.md``, which is
written to be sufficient for building a tenant without reading this
implementation. The names in ``__all__`` are that contract's hosting surface:
everything a program needs to compose and run its own tenants.
"""

from __future__ import annotations

from amoeba.process.errors import (
    AlreadyRunningError,
    GraceExpiredError,
    ProcessError,
    StartupFailedError,
    UpstreamShapeError,
)
from amoeba.process.host import ResidentProcess, Tenant
from amoeba.process.recovery import (
    Adopt,
    InFlight,
    NotApplied,
    Observation,
    Observer,
    Unknown,
)
from amoeba.process.settings import ProcessSettings
from amoeba.process.sq_outcome import (
    OUTCOME_EXIT_CODES,
    PollFailure,
    RunCheckpoint,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
    poll_run,
)
from amoeba.process.tenants import standard_tenants

__all__ = [
    "OUTCOME_EXIT_CODES",
    "Adopt",
    "AlreadyRunningError",
    "GraceExpiredError",
    "InFlight",
    "NotApplied",
    "Observation",
    "Observer",
    "PollFailure",
    "ProcessError",
    "ProcessSettings",
    "ResidentProcess",
    "RunCheckpoint",
    "RunOutcome",
    "RunOutcomeDocument",
    "RunPoll",
    "StartupFailedError",
    "Tenant",
    "Unknown",
    "UpstreamShapeError",
    "poll_run",
    "standard_tenants",
]
