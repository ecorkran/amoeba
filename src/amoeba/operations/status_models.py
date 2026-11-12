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
from amoeba.operations.decisions_models import MemberName
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.reject_codes import RejectCode


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


class StatusOutcome(StrEnum):
    LISTED = "listed"
    REJECTED = "rejected"


class StatusResult(_Model):
    """The result of ``status``. Fields that do not apply are null or empty."""

    outcome: StatusOutcome
    rejection: RejectCode | None = None
    programs: tuple[ProgramStatus, ...] = ()
    unplaced_runs: tuple[UnplacedRunEntry, ...] = ()
    problems: tuple[str, ...] = ()
