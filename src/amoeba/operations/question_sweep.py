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
from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.operations.question_judge import (
    RunFate,
    SweepResult,
    judge_in,
)
from amoeba.store.errors import StoreBusyError
from amoeba.store.models import QuestionRecord
from amoeba.store.question_closing import open_rows_of_run
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument

#: What a run reads as when ``sq runs wait --timeout 0`` times out: still going.
_STILL_RUNNING = "running"


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
    try:
        with store.write() as transaction:
            return judge_in(transaction, config, judged, now)
    except StoreBusyError as error:
        # Expected: another writer held the lock. The rows stay open and close at a
        # later call, and the caller still shows everything (it is in ``problem``).
        return SweepResult(problem=f"could not close stale questions: {error}")
