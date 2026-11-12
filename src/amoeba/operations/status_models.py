"""The values ``status`` returns (slice 224, D4, D8): pydantic models the CLI prints.

``WaitingRunState`` and ``UnplacedReason`` are defined here, once, and re-exported by
the modules that produce them. ``status`` re-exports the public models.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from amoeba.answering.values import DeclineReason
from amoeba.operations.calls_log import CallEntry
from amoeba.operations.decisions_models import MemberName
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.vocabulary import ClosedReason, ResumeOutcome


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RunFileUnreadable(StrEnum):
    """A run's ``pause`` when its run file cannot be read (not a ``PauseClass``)."""

    RUN_FILE_UNREADABLE = "run_file_unreadable"


class UnplacedReason(StrEnum):
    """Why a paused run could not be placed under a member."""

    NO_DIRECTORY = "no_directory"
    DIRECTORY_MISSING = "directory_missing"
    LOOKUP_FAILED = "lookup_failed"


class WaitingRunState(StrEnum):
    """Where the run of a waiting question is now (the ``run_state`` field). Not the
    answering decision's ``RunState`` (``answering.decide``), a different vocabulary."""

    AT_PAUSE = "at_pause"
    MOVED_ON = "moved_on"
    NOT_LISTED = "not_listed"


class NextOperation(StrEnum):
    """The operation a ``next`` entry names."""

    HANDLE_PAUSE = "handle_pause"
    ANSWER = "answer"


class NextAction(_Model):
    """The operation that handles an item, with the arguments to call it."""

    operation: NextOperation
    run_id: str
    paused_at: str | None = None
    #: Where to run it: the run's own checkout (``handle_pause``'s ``cwd``).
    directory: Path | None = None


class CheckpointEntry(_Model):
    kind: str | None
    paused_at: str | None
    question: str | None


class RunEntry(_Model):
    """A run placed under a member."""

    run_id: str
    pipeline: str
    #: Squadron's status text, raw.
    status: str
    working_directory: Path
    checkpoint: CheckpointEntry | None
    #: Null for a run that is not paused.
    pause: PauseClass | RunFileUnreadable | None
    detail: str | None
    next: NextAction | None
    #: For an ``unhandled`` or ``claim_stale`` run: the newest calls-log line for it,
    #: which shows why a hook missed. Null when none was logged (D11).
    last_call: CallEntry | None = None


class WaitingEntry(_Model):
    """A question waiting on the PM, joined to its run by ``run_id``."""

    run_id: str
    paused_at: str
    question: str
    slice_label: str | None
    waiting_reason: DeclineReason | None
    waiting_detail: str | None
    #: When the question was first recorded.
    since: datetime
    run_state: WaitingRunState
    #: For ``moved_on``: the run's state now.
    detail: str | None
    next: NextAction | None


class MemberStatus(_Model):
    member: MemberName
    runs: tuple[RunEntry, ...]
    waiting_on_pm: tuple[WaitingEntry, ...]


class ProgramStatus(_Model):
    program: str
    members: tuple[MemberStatus, ...]


class UnplacedRunEntry(_Model):
    """A paused run no member could be found for."""

    run_id: str
    status: str
    reason: UnplacedReason
    #: The checkpoint's kind, raw; null when the listing gave none.
    checkpoint_kind: str | None
    #: For ``lookup_failed``: the error text.
    detail: str | None = None


class ClosedNowEntry(_Model):
    """A question this call closed, or an answer it marked ``not_delivered`` (D12).

    For a closed question ``closed_reason`` is set and ``answer_seq`` is null; for an
    answer marked ``not_delivered`` it is the other way round. ``closed_detail`` is
    the run's state in both.
    """

    program: str
    member: MemberName
    run_id: str
    paused_at: str
    question: str
    closed_reason: ClosedReason | None
    closed_detail: str
    answer_seq: int | None = None
    resume_outcome: ResumeOutcome | None = None


class StatusOutcome(StrEnum):
    LISTED = "listed"
    REJECTED = "rejected"


class StatusResult(_Model):
    """The result of ``status``. Fields that do not apply are null or empty."""

    outcome: StatusOutcome
    rejection: RejectCode | None = None
    programs: tuple[ProgramStatus, ...] = ()
    unplaced_runs: tuple[UnplacedRunEntry, ...] = ()
    #: What this call closed, so the PM sees each automatic closure once (D12).
    closed_now: tuple[ClosedNowEntry, ...] = ()
    #: Set when the sweep could not take the store's lock; nothing was closed.
    sweep_problem: str | None = None
    #: Calls-log files that could not be read, and entries prune could not remove, D12.
    file_problems: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()
