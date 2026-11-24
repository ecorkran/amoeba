"""The shared resume: hand an answer back to the paused run (slice 223, D8).

Both ``handle_pause`` and ``answer`` call :func:`resume`. The run is judged by what
Squadron says about it after the resume child starts, never by the child's exit code
or its text: ``running``, or moved past this pause, is ``resumed``; a child that is
gone with the run still at this pause is ``refused``. ``resumed`` and
``not_delivered`` are final in the store, so a racing second resume cannot overwrite
the first's outcome. No store transaction is open while a child runs or Squadron is
polled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final

from amoeba.answering.gate import compose_instructions
from amoeba.operations.deps import Deps
from amoeba.operations.pause_models import ResumeResult
from amoeba.operations.processes import WaitableChild, terminate_group
from amoeba.operations.resume_attempt import (
    RESUME_LOG_DIRECTORY,
    attempt_path,
    read_attempt,
    write_judged,
    write_started,
)
from amoeba.operations.resume_timing import (
    RESUME_POLL_INTERVAL_SECONDS,
)
from amoeba.operations.steps.models import (
    RESUME_RECORD,
    ResumeClaimPayload,
    ResumeRecordRequest,
)
from amoeba.operations.store_steps import Steps
from amoeba.store.models import QuestionKey
from amoeba.store.vocabulary import ResumeOutcome
from amoeba.upstream.bounded_text import cut_to_bound
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs, stderr_tail
from amoeba.upstream.squadron.resume_argv import resume_argv
from amoeba.upstream.squadron.run_outcome import (
    PollFailure,
    RunOutcome,
    RunOutcomeDocument,
)

#: The outcomes the store never overwrites (``resumed`` and ``not_delivered``).
FINAL_OUTCOMES: Final = frozenset({ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED})
EARLIER_ATTEMPT_DETAIL: Final = (
    "an earlier attempt started the resume and stopped before it recorded an outcome"
)
LOG_STAMP_FORMAT: Final = "%Y%m%dT%H%M%S%fZ"


class _Seen(StrEnum):
    """Where a poll shows the run, relative to the pause being answered."""

    AT_PAUSE = "at_pause"
    RUNNING = "running"
    MOVED_PAST = "moved_past"
    #: Not found, unreadable, an unknown status, or a poll that failed.
    UNCLEAR = "unclear"


class ResumeUnreadableError(SquadronError):
    """The first poll could not be read and no earlier attempt had started the resume,
    so the outcome ``refused`` was recorded and the claim freed (D6).

    ``handle_pause`` lets it propagate (exit 3, as an unreadable poll always was);
    ``answer`` returns ``result`` as the resume's outcome.
    """

    def __init__(self, reason: str, result: ResumeResult) -> None:
        super().__init__(reason)
        self.result = result


def resume(steps: Steps, claimed: ResumeClaimPayload, deps: Deps) -> ResumeResult:
    """Resume the claimed answer's run and record the outcome (D6).

    The caller holds the claim; the attempt file on this machine says what an earlier
    attempt for the answer did. The result is what the store holds: if the answer's
    outcome was already final, that outcome, not this attempt's.

    Raises:
        ResumeUnreadableError: The first poll could not be read and ``refused`` was
            recorded.
        SquadronError: The first poll could not be read and an earlier attempt's file
            holds ``started``: nothing is recorded, because that attempt may have
            resumed the run.
        HubUnreachableError, HubRefusedError: A step got no reply, or was refused.
    """
    key = QuestionKey(claimed.run_id, claimed.paused_at)
    path = attempt_path(deps.logs_dir, key.run_id, claimed.answer_seq)
    judged = _judge(claimed, key, path, deps)
    if not judged.replayed:
        write_judged(path, judged.outcome, judged.detail, judged.resume_log)
    recorded = steps.run(
        RESUME_RECORD,
        ResumeRecordRequest(
            answer_seq=claimed.answer_seq,
            claim_id=claimed.claim_id,
            outcome=judged.outcome,
            detail=judged.detail,
            log=judged.resume_log,
        ),
    )
    result = ResumeResult(recorded.outcome, recorded.detail, recorded.log)
    if judged.unreadable is not None:
        raise ResumeUnreadableError(judged.unreadable, result)
    return result


@dataclass(frozen=True)
class _Judged:
    """What this attempt came to, before it is recorded."""

    outcome: ResumeOutcome
    detail: str | None
    resume_log: str | None
    #: The outcome came from the attempt file: it is in the file already.
    replayed: bool = False
    #: Set when the first poll could not be read, to the reason.
    unreadable: str | None = None


def _judge(
    claimed: ResumeClaimPayload, key: QuestionKey, path: Path, deps: Deps
) -> _Judged:
    """Judge the attempt by D6's table: the file first, then the run."""
    earlier = read_attempt(path)
    if (
        earlier is not None
        and earlier.outcome is not None
        and earlier.outcome in FINAL_OUTCOMES
    ):
        # A lost record: the earlier attempt judged this and its record did not land.
        return _Judged(earlier.outcome, earlier.detail, earlier.log, replayed=True)
    first = deps.poll_run(key.run_id)
    if isinstance(first, PollFailure):
        if earlier is not None and earlier.is_started:
            # That attempt may have resumed the run, so a refused here would be
            # false, and writing it would lose ``started``: record nothing.
            raise SquadronError(first.reason)
        return _Judged(
            ResumeOutcome.REFUSED,
            cut_to_bound(first.reason),
            None,
            unreadable=first.reason,
        )
    seen = _seen(first, key)
    if seen is not _Seen.AT_PAUSE:
        if earlier is not None and earlier.is_started:
            return _Judged(ResumeOutcome.RESUMED, EARLIER_ATTEMPT_DETAIL, None)
        return _Judged(
            ResumeOutcome.NOT_DELIVERED, _not_delivered_detail(first, seen), None
        )
    write_started(path)
    logs = _resume_logs(deps, key.run_id, claimed.answer_seq)
    # The text is one argv element behind ``--instructions`` (no shell), and it always
    # starts with the fixed "You asked: ", so neither the question nor the answer can
    # be read as an option or as a second argument, whatever they contain.
    argv = resume_argv(
        key.run_id, compose_instructions(claimed.question, claimed.answer_text)
    )
    child = deps.spawn(argv, Path(claimed.checkout), logs)
    if isinstance(child, LaunchError):
        return _Judged(ResumeOutcome.REFUSED, cut_to_bound(child.detail), None)
    followed = _follow(child, key, logs, deps, claimed.resume_wait_seconds)
    return _Judged(followed.outcome, followed.detail, followed.resume_log)


def _resume_logs(deps: Deps, run_id: str, answer_seq: int) -> LaunchLogs:
    stamp = deps.clock().strftime(LOG_STAMP_FORMAT)
    directory = deps.logs_dir / RESUME_LOG_DIRECTORY / run_id
    return LaunchLogs(
        stdout=directory / f"{answer_seq}-{stamp}.stdout.log",
        stderr=directory / f"{answer_seq}-{stamp}.stderr.log",
    )


def _follow(
    child: WaitableChild,
    key: QuestionKey,
    logs: LaunchLogs,
    deps: Deps,
    wait_seconds: float,
) -> ResumeResult:
    """Poll until the run moves, the child gives up, or ``wait_seconds`` pass."""
    log = str(logs.stdout)
    deadline = deps.clock() + timedelta(seconds=wait_seconds)
    while True:
        seen = _poll_seen(deps, key)
        if seen in (_Seen.RUNNING, _Seen.MOVED_PAST):
            return ResumeResult(ResumeOutcome.RESUMED, None, log)
        if child.poll() is not None:
            return ResumeResult(ResumeOutcome.REFUSED, _exit_detail(logs, seen), log)
        if deps.clock() >= deadline:
            break
        deps.sleep(RESUME_POLL_INTERVAL_SECONDS)
    return _after_timeout(child, key, deps, wait_seconds, log)


def _after_timeout(
    child: WaitableChild,
    key: QuestionKey,
    deps: Deps,
    wait_seconds: float,
    log: str,
) -> ResumeResult:
    """The child is alive and the run unchanged: stop it, then look once more, since
    it may have taken the run just before it was stopped."""
    terminate_group(child)
    if _poll_seen(deps, key) in (_Seen.RUNNING, _Seen.MOVED_PAST):
        return ResumeResult(
            ResumeOutcome.RESUMED, "resume process terminated after taking the run", log
        )
    return ResumeResult(
        ResumeOutcome.REFUSED, f"not running after {wait_seconds:g} seconds", log
    )


def _poll_seen(deps: Deps, key: QuestionKey) -> _Seen:
    polled = deps.poll_run(key.run_id)
    if isinstance(polled, PollFailure):
        return _Seen.UNCLEAR
    return _seen(polled, key)


def _seen(document: RunOutcomeDocument, key: QuestionKey) -> _Seen:
    match document.outcome:
        case RunOutcome.TIMED_OUT:
            # With ``--timeout 0`` this is how a run that is still going reads.
            return _Seen.RUNNING
        case RunOutcome.PAUSED:
            paused_at = (
                None
                if document.checkpoint is None
                else (document.checkpoint.paused_at_text)
            )
            return _Seen.AT_PAUSE if paused_at == key.paused_at else _Seen.MOVED_PAST
        case RunOutcome.COMPLETED | RunOutcome.FAILED | RunOutcome.ORPHANED:
            return _Seen.MOVED_PAST
        case _:
            return _Seen.UNCLEAR


def _not_delivered_detail(document: RunOutcomeDocument, seen: _Seen) -> str:
    if seen is _Seen.UNCLEAR:
        return f"the run could not be read: outcome {document.outcome.value}"
    if seen is _Seen.RUNNING:
        return "the run is already running"
    return f"the run is no longer at this pause: outcome {document.outcome.value}"


def _exit_detail(logs: LaunchLogs, seen: _Seen) -> str:
    """Why the child gave up: its stderr tail, else its stdout tail (the real ``sq``
    prints a held run lock on stdout), else a note of what was seen."""
    for path in (logs.stderr, logs.stdout):
        tail = _tail(path)
        if tail.strip():
            return cut_to_bound(tail.strip())
    if seen is _Seen.UNCLEAR:
        return "the resume process exited and the run could not be read"
    return "the resume process exited and the run is still at the pause"


def _tail(path: Path) -> str:
    try:
        return stderr_tail(path)
    except OSError as error:
        # Expected: the log is unreadable; the detail says so instead of its text.
        return f"log {path.name} unreadable: {error}"
