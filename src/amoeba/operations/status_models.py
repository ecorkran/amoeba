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
from amoeba.operations.message_results import RequestDirection, WakeWaitingOn
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.vocabulary import (
    ClosedReason,
    RequestState,
    ResumeOutcome,
    WakeOutcome,
)


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
    #: For an ``unhandled``, ``claim_stale`` or ``waiting_on_request`` run: the newest
    #: calls-log line for it, which shows why a hook or a start missed. Null when none
    #: was logged (D11, 242 D9).
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
    #: The request behind a ``request_*`` waiting reason; else null (242 D9).
    request_id: str | None = None
    #: The machine the run paused on (262 D14); null for a question whose machine was
    #: removed.
    machine: str | None = None
    #: When that machine last called the hub, set only when it is not the calling one:
    #: an answer for it waits for its next call (262 D7).
    machine_last_called_at: str | None = None


class RequestEntry(_Model):
    """An open or accepted request a member sent or received (slice 240, D12)."""

    id: str
    direction: RequestDirection
    #: The member at the other end: its project id, and its stored name (261 D13).
    other_member: str
    other_name: str
    subject: str
    #: The effective state: an open request past its expiry reads ``expired``.
    state: RequestState
    created_at: datetime
    state_changed_at: datetime
    parent_id: str | None
    #: The live requests whose parent is this one: what this request is waiting on.
    child_ids: tuple[str, ...]


class RejectedCall(_Model):
    """A ``send``, ``reply`` or ``cancel`` the member made that was refused."""

    operation: str
    code: str
    #: The recipient as given; ``send`` only.
    to_ref: str | None
    message_id: str | None
    parent_id: str | None
    detail: str
    created_at: datetime


class SessionEntry(_Model):
    """A live ``amoeba-mcp`` session serving the member (slice 241, D8)."""

    client: str
    directory: str
    started_at: datetime
    heartbeat_at: datetime
    #: When its agent first answered a channel event; ``None`` while unconfirmed.
    push_confirmed_at: datetime | None


class WakeRunning(_Model):
    """The member's wake that has not been recorded as ended (slice 244, D9)."""

    started_at: datetime
    deadline_at: datetime
    #: The command's pid, also its process group id; null until it started, or when
    #: the store was held while the wrapper wrote it.
    command_pid: int | None
    #: The log files' path without the ``.stdout.log`` and ``.stderr.log`` suffix.
    log_stem: str | None
    #: True once ``deadline_at`` has passed with the row still unended: no end was
    #: recorded, so its wrapper is probably gone. It no longer counts as a live wake, so
    #: the member can be woken again.
    overdue: bool


class WakeStopped(_Model):
    """Waking is stopped: the member has used its wakes of the last 24 hours."""

    used: int
    limit: int


class WakeLastProblem(_Model):
    """The member's newest ended wake, when it went wrong."""

    outcome: WakeOutcome
    exit_code: int | None
    #: An exception class and its OS message, never the command's text.
    detail: str | None
    ended_at: datetime
    log_stem: str | None


class WakeStatus(_Model):
    """Waking for a member that has a wake command (slice 244, D9)."""

    #: The member's wake command, in plain text.
    command: str
    #: The machine whose checkout's command this is (262 D8).
    machine: str | None = None
    #: Machines a due wake waits for, each with when it last called the hub (262 D8).
    waiting_on: tuple[WakeWaitingOn, ...] = ()
    running: WakeRunning | None
    stopped: WakeStopped | None
    last_problem: WakeLastProblem | None


class MemberStatus(_Model):
    member: MemberName
    runs: tuple[RunEntry, ...]
    waiting_on_pm: tuple[WaitingEntry, ...]
    requests: tuple[RequestEntry, ...] = ()
    #: The member's retained rejections, newest first.
    rejected_calls: tuple[RejectedCall, ...] = ()
    #: The member's live sessions, oldest first (slice 241, D8).
    sessions: tuple[SessionEntry, ...] = ()
    #: Waking, present only for a member with a wake command (slice 244, D9).
    wake: WakeStatus | None = None


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
    #: Says request subjects, rejected-call recipients and request reasons are other
    #: agents' text; set when any member shows a request, a rejected call, a held run
    #: or a waiting entry from a request, else null (240 D11, 242 D9).
    notice: str | None = None
    programs: tuple[ProgramStatus, ...] = ()
    unplaced_runs: tuple[UnplacedRunEntry, ...] = ()
    #: What this call closed, so the PM sees each automatic closure once (D12).
    closed_now: tuple[ClosedNowEntry, ...] = ()
    #: Set when the sweep could not take the store's lock; nothing was closed.
    sweep_problem: str | None = None
    #: Calls-log files that could not be read, and entries prune could not remove, D12.
    file_problems: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()
