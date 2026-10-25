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
from amoeba.process.observers.cf_get import CF_FIELD_FILE_SLICE
from amoeba.process.observers.cf_readback import (
    RESULT_FILE_SLICE,
    RESULT_PROJECT_PATH,
    RESULT_UPDATED_AT,
    RESULT_WORKTREE_ID,
    CFRun,
    ReadBackAnswer,
    ReadFailed,
    read_back_answer,
)
from amoeba.process.recovery import (
    Adopt,
    InFlight,
    NotApplied,
    Observation,
    Observer,
    Unknown,
)
from amoeba.process.review_scan import detection_key, ledger_key
from amoeba.process.settings import ProcessSettings
from amoeba.process.sq_outcome import (
    OUTCOME_EXIT_CODES,
    SQ_EXECUTABLE,
    SQ_USAGE_ERROR_EXIT_CODE,
    CheckpointKind,
    FailureKind,
    PollFailure,
    RunCheckpoint,
    RunFailure,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
    RunReview,
    UnknownKind,
    parse_checkpoint_kind,
    parse_failure_kind,
    poll_run,
)
from amoeba.process.tenants import standard_tenants
from amoeba.process.version_label import capture_sq_version_label

__all__ = [
    "CF_FIELD_FILE_SLICE",
    "RESULT_FILE_SLICE",
    "RESULT_PROJECT_PATH",
    "RESULT_UPDATED_AT",
    "RESULT_WORKTREE_ID",
    "OUTCOME_EXIT_CODES",
    "SQ_EXECUTABLE",
    "SQ_USAGE_ERROR_EXIT_CODE",
    "Adopt",
    "CFRun",
    "ReadBackAnswer",
    "ReadFailed",
    "AlreadyRunningError",
    "CheckpointKind",
    "FailureKind",
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
    "RunFailure",
    "RunOutcome",
    "RunOutcomeDocument",
    "RunPoll",
    "RunReview",
    "StartupFailedError",
    "Tenant",
    "Unknown",
    "UnknownKind",
    "UpstreamShapeError",
    "capture_sq_version_label",
    "detection_key",
    "ledger_key",
    "parse_checkpoint_kind",
    "parse_failure_kind",
    "read_back_answer",
    "poll_run",
    "standard_tenants",
]
