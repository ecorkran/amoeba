"""The automatic close sweep: close open questions whose run has left their pause
(slice 228, D4).

A question is *open* when it is ``claimed`` or ``waiting_on_pm``, or ``answered`` with
its latest answer unresumed. Given what Squadron says about the run (:class:`RunFate`),
each open row is judged by the D4 table and closed by compare-and-set in one short
write transaction, so a concurrent ``answer``, ``dismiss`` or settle wins and the
sweep skips that row. No transaction is held across a subprocess: the callers poll
first and sweep after.

A busy lock on the sweep's write is the one error caught here: a closure that lost a
lock must not hide the PM's waiting list, so it is returned as ``problem`` and the
rows close at a later call. Any other ``StoreError`` propagates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from amoeba.config.user_config import UserConfig
from amoeba.operations.resume import resume_bound_seconds
from amoeba.store.answers import latest_answer, mark_not_delivered
from amoeba.store.errors import StoreBusyError
from amoeba.store.models import AnswerRecord, QuestionKey, QuestionRecord
from amoeba.store.question_closing import close_question, open_rows_of_run
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument

#: What a run reads as when ``sq runs wait --timeout 0`` times out: still going.
_STILL_RUNNING = "running"


@dataclass(frozen=True)
class RunFate:
    """Where a run is now, as far as it matters to its older open questions."""

    #: ``RUN_MOVED_ON`` or ``RUN_GONE``.
    reason: ClosedReason
    #: The run's state, or the later pause, recorded as ``closed_detail``.
    detail: str
    #: The pause the run is at now; a row there is never touched. ``None`` when the
    #: run is not paused.
    current_paused_at: str | None


@dataclass(frozen=True)
class ClosedQuestion:
    """A question this sweep closed."""

    key: QuestionKey
    member_id: str
    question: str
    closed_reason: ClosedReason
    closed_detail: str


@dataclass(frozen=True)
class UndeliveredAnswer:
    """An answer this sweep marked ``not_delivered``."""

    key: QuestionKey
    member_id: str
    question: str
    answer_seq: int
    resume_outcome: ResumeOutcome
    detail: str


@dataclass(frozen=True)
class SweepResult:
    """What a sweep closed, and why it could not if its write lost the lock."""

    closed: tuple[ClosedQuestion, ...] = ()
    undelivered: tuple[UndeliveredAnswer, ...] = ()
    #: Set when the write could not take the lock; nothing was closed.
    problem: str | None = None

    @property
    def changed_anything(self) -> bool:
        return bool(self.closed or self.undelivered)


def sweep_note(result: SweepResult) -> str | None:
    """One line for a calls-log or result ``detail``: what the sweep closed or why it
    could not. ``None`` when it did nothing."""
    parts = [
        f"closed the question at {item.key.paused_at} as {item.closed_reason} "
        f"({item.closed_detail})"
        for item in result.closed
    ]
    parts += [
        f"marked answer {item.answer_seq} not_delivered ({item.detail})"
        for item in result.undelivered
    ]
    if result.problem is not None:
        parts.append(result.problem)
    return "; ".join(parts) if parts else None


def fate_of_poll(polled: RunOutcomeDocument) -> RunFate | None:
    """The fate a ``sq runs wait`` document gives, or ``None`` when it cannot say
    (an unreadable run or an unknown status closes nothing)."""
    match polled.outcome:
        case RunOutcome.PAUSED:
            checkpoint = polled.checkpoint
            paused_at = None if checkpoint is None else checkpoint.paused_at_text
            if paused_at is None:
                # Which pause is current is unknown, so no row can be called old.
                return None
            return RunFate(
                ClosedReason.RUN_MOVED_ON, f"paused at {paused_at}", paused_at
            )
        case RunOutcome.NOT_FOUND:
            return RunFate(ClosedReason.RUN_GONE, polled.outcome.value, None)
        case RunOutcome.TIMED_OUT:
            return RunFate(ClosedReason.RUN_MOVED_ON, _STILL_RUNNING, None)
        case RunOutcome.COMPLETED | RunOutcome.FAILED | RunOutcome.ORPHANED:
            return RunFate(ClosedReason.RUN_MOVED_ON, polled.outcome.value, None)
        case RunOutcome.UNREADABLE | RunOutcome.UNKNOWN_STATUS:
            return None


def sweep_run(
    store: Store,
    config: UserConfig,
    run_id: str,
    polled: RunOutcomeDocument,
    now: datetime,
) -> SweepResult:
    """Close the run's open rows at any pause other than its current one.

    ``polled`` is the poll ``handle_pause`` already made. If the run is no longer
    paused, every open row of it is judged.

    Raises:
        StoreError: Anything but a busy lock (which is reported as ``problem``).
    """
    fate = fate_of_poll(polled)
    if fate is None:
        return SweepResult()
    with store.read() as transaction:
        rows = open_rows_of_run(transaction, run_id)
    judged = [
        (row, fate) for row in rows if row.key.paused_at != fate.current_paused_at
    ]
    return apply_sweep(store, config, judged, now)


def apply_sweep(
    store: Store,
    config: UserConfig,
    judged: Sequence[tuple[QuestionRecord, RunFate]],
    now: datetime,
) -> SweepResult:
    """Apply the D4 table to each (row, fate) in one short write transaction."""
    if not judged:
        return SweepResult()
    closed: list[ClosedQuestion] = []
    undelivered: list[UndeliveredAnswer] = []
    try:
        with store.write() as transaction:
            for row, fate in judged:
                _judge(transaction, config, row, fate, now, closed, undelivered)
    except StoreBusyError as error:
        # Expected: another writer held the lock. The rows stay open and close at a
        # later call, and the caller still shows everything (it is in ``problem``).
        return SweepResult(problem=f"could not close stale questions: {error}")
    return SweepResult(tuple(closed), tuple(undelivered))


def _judge(  # noqa: PLR0913 - one row of the D4 table and its outputs
    transaction: Transaction,
    config: UserConfig,
    row: QuestionRecord,
    fate: RunFate,
    now: datetime,
    closed: list[ClosedQuestion],
    undelivered: list[UndeliveredAnswer],
) -> None:
    match row.state:
        case QuestionState.WAITING_ON_PM:
            _close(transaction, row, fate, now, closed)
        case QuestionState.CLAIMED:
            # A young claim is left alone: its answering run may still settle.
            if now - row.claimed_at >= timedelta(seconds=config.answering_wait_seconds):
                _close(transaction, row, fate, now, closed)
        case QuestionState.ANSWERED:
            _mark_undelivered(transaction, config, row, fate, now, undelivered)
        case QuestionState.CLOSED:
            return


def _close(
    transaction: Transaction,
    row: QuestionRecord,
    fate: RunFate,
    now: datetime,
    closed: list[ClosedQuestion],
) -> None:
    if close_question(
        transaction, row.key, fate.reason, fate.detail, row.state, row.updated_at, now
    ):
        closed.append(
            ClosedQuestion(
                row.key, row.member_id, row.question, fate.reason, fate.detail
            )
        )


def _mark_undelivered(  # noqa: PLR0913 - one row of the D4 table and its output
    transaction: Transaction,
    config: UserConfig,
    row: QuestionRecord,
    fate: RunFate,
    now: datetime,
    undelivered: list[UndeliveredAnswer],
) -> None:
    # Read again inside this transaction: a resume or a new answer since the caller's
    # read moves the newest sign of life, and this write is serialized with them.
    latest = latest_answer(transaction, row.key)
    if latest is None or latest.resume_outcome not in (None, ResumeOutcome.REFUSED):
        return
    if now - _newest_sign(latest) < timedelta(seconds=resume_bound_seconds(config)):
        return
    if mark_not_delivered(transaction, latest.seq, fate.detail, now=now):
        undelivered.append(
            UndeliveredAnswer(
                row.key,
                row.member_id,
                row.question,
                latest.seq,
                ResumeOutcome.NOT_DELIVERED,
                fate.detail,
            )
        )


def _newest_sign(answer: AnswerRecord) -> datetime:
    """The newest of when the answer was recorded, its resume started and its last
    outcome was recorded: the last time anything was in flight for it."""
    return max(
        moment
        for moment in (answer.recorded_at, answer.resume_started_at, answer.resume_at)
        if moment is not None
    )
