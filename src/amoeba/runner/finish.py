"""Record a finished run: block the node if a human must look, then resolve.

A run that ended (or vanished) is ingested by ``ingest.record``: its outcome's block,
its last review recorded, the entry resolved (125). A launch that never produced a
run stays here (122). Either way the order is block, then resolve, and both writes
are idempotent on re-entry: a crash between them leaves an unresolved entry, so the
next tick observes it again, finds the node already blocked, and finishes the
sequence.
"""

from __future__ import annotations

from typing import Final

from amoeba.runner.ingest.outcome import PAYLOAD_REASON, PAYLOAD_RUN_ID, BlockPlan
from amoeba.runner.ingest.record import RESULT_RUN_ID, block_once, ingest
from amoeba.runner.observed import Finished, LaunchFailed, RunEnded, RunVanished
from amoeba.store import (
    PARAM_RUN_ID,
    BlockedKind,
    JournalEntry,
    JournalOutcome,
    Store,
)

#: Result and payload keys of a failed launch.
RESULT_LAUNCH_FAILURE: Final = "launch_failure"
PAYLOAD_EXIT_CODE: Final = "exit_code"
PAYLOAD_STDERR_TAIL: Final = "stderr_tail"


def record(
    store: Store, entry: JournalEntry, finished: Finished, version_label: str
) -> None:
    """Block the entry's node when a human must look, then resolve the entry.

    ``version_label`` is the ``sq --version`` label captured once at start-up; it
    labels a recorded review whose file carries no stamp of its own.
    """
    match finished:
        case RunEnded() | RunVanished():
            ingest(store, entry, finished, version_label)
        case LaunchFailed():
            _record_launch_failed(store, entry, finished)


def _record_launch_failed(
    store: Store, entry: JournalEntry, finished: LaunchFailed
) -> None:
    run_id = _run_id(entry)
    code = "unknown" if finished.exit_code is None else str(finished.exit_code)
    context = (
        f"launch of {run_id} failed ({finished.failure.value}); "
        f"exit code {code}; stderr: {finished.tail}"
    )
    payload: dict[str, object] = {
        PAYLOAD_RUN_ID: run_id,
        PAYLOAD_REASON: finished.failure.value,
        PAYLOAD_EXIT_CODE: finished.exit_code,
        PAYLOAD_STDERR_TAIL: finished.tail,
    }
    block_once(store, entry.node_id, BlockPlan(BlockedKind.HUMAN, context, payload))
    store.journal_resolve(
        entry.id,
        outcome=JournalOutcome.FAILED,
        result={RESULT_RUN_ID: run_id, RESULT_LAUNCH_FAILURE: finished.failure.value},
    )


def _run_id(entry: JournalEntry) -> str:
    run_id = entry.parameters.get(PARAM_RUN_ID)
    if not isinstance(run_id, str) or not run_id:
        raise ValueError(f"entry {entry.id} has an unusable run id: {run_id!r}")
    return run_id
