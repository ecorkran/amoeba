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

from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final

from amoeba.answering.gate import compose_instructions
from amoeba.operations.deps import Deps
from amoeba.operations.pause_models import ResumeResult
from amoeba.operations.processes import WaitableChild, terminate_group
from amoeba.store.answers import get_answer, record_resume
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.store import Store
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

#: How often the run is polled while the resume child is starting (D8).
RESUME_POLL_INTERVAL_SECONDS: Final = 0.5

RESUME_LOG_DIRECTORY: Final = "resume"
LOG_STAMP_FORMAT: Final = "%Y%m%dT%H%M%S%fZ"


class _Seen(StrEnum):
    """Where a poll shows the run, relative to the pause being answered."""

    AT_PAUSE = "at_pause"
    RUNNING = "running"
    MOVED_PAST = "moved_past"
    #: Not found, unreadable, an unknown status, or a poll that failed.
    UNCLEAR = "unclear"


def resume(
    store: Store,
    question: QuestionRecord,
    answer_seq: int,
    *,
    deps: Deps,
    wait_seconds: float,
) -> ResumeResult:
    """Resume the question's run with the answer ``answer_seq`` and record the outcome.

    Raises:
        SquadronError: The first poll could not be read (the state is unknown, so
            nothing is started and nothing is written).
        ValueError: ``answer_seq`` is not an answer to this question.
    """
    with store.read() as transaction:
        answer = get_answer(transaction, answer_seq)
    if answer is None or answer.key != question.key:
        raise ValueError(f"answer {answer_seq} is not an answer to {question.key}")
    result = _attempt(question, answer.answer, answer_seq, deps, wait_seconds)
    with store.write() as transaction:
        record_resume(
            transaction,
            answer_seq,
            result.outcome,
            detail=result.detail,
            log=result.resume_log,
            at=deps.clock(),
        )
    return result


def _attempt(
    question: QuestionRecord,
    answer_text: str,
    answer_seq: int,
    deps: Deps,
    wait_seconds: float,
) -> ResumeResult:
    first = deps.poll_run(question.key.run_id)
    if isinstance(first, PollFailure):
        raise SquadronError(first.reason)
    seen = _seen(first, question.key)
    if seen is not _Seen.AT_PAUSE:
        return ResumeResult(
            ResumeOutcome.NOT_DELIVERED, _not_delivered_detail(first, seen), None
        )
    logs = _resume_logs(deps, question.key.run_id, answer_seq)
    # The text is one argv element behind ``--instructions`` (no shell), and it always
    # starts with the fixed "You asked: ", so neither the question nor the answer can
    # be read as an option or as a second argument, whatever they contain.
    argv = resume_argv(
        question.key.run_id, compose_instructions(question.question, answer_text)
    )
    child = deps.spawn(argv, Path(question.checkout), logs)
    if isinstance(child, LaunchError):
        return ResumeResult(ResumeOutcome.REFUSED, cut_to_bound(child.detail), None)
    return _follow(child, question.key, logs, deps, wait_seconds)


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
