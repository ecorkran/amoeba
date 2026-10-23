"""Record a finished run: block the node if a human must look, then resolve.

The body is deliberately minimal (D2). Reviews, checkpoint blocked-states and
routing come with 125 and 126, which replace :func:`record`. The order is always
block, then resolve, and both writes are idempotent on re-entry: a crash between
them leaves an unresolved entry whose run still exists, so the next tick
observes the run again, finds the node already blocked, and finishes the
sequence.
"""

from __future__ import annotations

from typing import Final

from amoeba.process import RunOutcome
from amoeba.runner.observe import Finished, LaunchFailed, RunEnded, RunVanished
from amoeba.store import (
    PARAM_RUN_ID,
    BlockedKind,
    JournalEntry,
    JournalOutcome,
    Store,
)

#: Result and payload keys.
RESULT_RUN_ID: Final = PARAM_RUN_ID
RESULT_OUTCOME: Final = "outcome"
RESULT_STATUS: Final = "status"
RESULT_CHECKPOINT: Final = "checkpoint"
RESULT_PAUSED_AT: Final = "paused_at"
RESULT_LAUNCH_FAILURE: Final = "launch_failure"
PAYLOAD_REASON: Final = "reason"
PAYLOAD_EXIT_CODE: Final = "exit_code"
PAYLOAD_STDERR_TAIL: Final = "stderr_tail"

#: The block reason for a confirmed run that Squadron no longer knows.
REASON_VANISHED: Final = "vanished"


def record(store: Store, entry: JournalEntry, finished: Finished) -> None:
    """Block the entry's node when a human must look, then resolve the entry."""
    match finished:
        case RunEnded():
            _record_ended(store, entry, finished)
        case RunVanished():
            _block_once(
                store,
                entry,
                REASON_VANISHED,
                f"run {_run_id(entry)} vanished: Squadron has no state for it",
            )
            store.journal_resolve(
                entry.id,
                outcome=JournalOutcome.FAILED,
                result={RESULT_RUN_ID: _run_id(entry), RESULT_OUTCOME: REASON_VANISHED},
            )
        case LaunchFailed():
            _record_launch_failed(store, entry, finished)


def _record_ended(store: Store, entry: JournalEntry, finished: RunEnded) -> None:
    document = finished.document
    run_id = _run_id(entry)
    result: dict[str, object] = {
        RESULT_RUN_ID: run_id,
        RESULT_OUTCOME: document.outcome.value,
        RESULT_STATUS: document.status,
    }
    match document.outcome:
        case RunOutcome.COMPLETED:
            pass
        case RunOutcome.FAILED:
            _block_once(store, entry, document.outcome.value, f"run {run_id} failed")
        case RunOutcome.PAUSED:
            paused_at = document.checkpoint.paused_at if document.checkpoint else None
            result[RESULT_CHECKPOINT] = {
                RESULT_PAUSED_AT: paused_at.isoformat() if paused_at else None
            }
            _block_once(store, entry, document.outcome.value, f"run {run_id} paused")
        case RunOutcome.ORPHANED:
            _block_once(
                store, entry, document.outcome.value, f"run {run_id} was orphaned"
            )
            # The command could not finish.
            store.journal_resolve(
                entry.id, outcome=JournalOutcome.FAILED, result=result
            )
            return
        case _:
            raise ValueError(
                f"run {run_id} outcome {document.outcome.value} is not an end state"
            )
    store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED, result=result)


def _record_launch_failed(
    store: Store, entry: JournalEntry, finished: LaunchFailed
) -> None:
    run_id = _run_id(entry)
    code = "unknown" if finished.exit_code is None else str(finished.exit_code)
    context = (
        f"launch of {run_id} failed ({finished.failure.value}); "
        f"exit code {code}; stderr: {finished.tail}"
    )
    _block_once(
        store,
        entry,
        finished.failure.value,
        context,
        {PAYLOAD_EXIT_CODE: finished.exit_code, PAYLOAD_STDERR_TAIL: finished.tail},
    )
    store.journal_resolve(
        entry.id,
        outcome=JournalOutcome.FAILED,
        result={RESULT_RUN_ID: run_id, RESULT_LAUNCH_FAILURE: finished.failure.value},
    )


def _block_once(
    store: Store,
    entry: JournalEntry,
    reason: str,
    context: str,
    extra: dict[str, object] | None = None,
) -> None:
    """Block the entry's node on a human, unless it is already blocked."""
    if store.blocked_state_for(entry.node_id) is not None:
        return
    store.block(
        entry.node_id,
        kind=BlockedKind.HUMAN,
        context=context,
        payload={
            RESULT_RUN_ID: _run_id(entry),
            PAYLOAD_REASON: reason,
            **(extra or {}),
        },
    )


def _run_id(entry: JournalEntry) -> str:
    run_id = entry.parameters.get(PARAM_RUN_ID)
    if not isinstance(run_id, str):
        raise ValueError(f"entry {entry.id} has an unusable run id: {run_id!r}")
    return run_id
