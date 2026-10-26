"""Record a finished run: block the node if a human must look, then resolve.

A run that ended (or vanished) is ingested by ``ingest.record``: its outcome's block,
its last review recorded, the entry resolved (125). A launch that never produced a
run stays here (122). Either way the order is block, then resolve, and both writes
are idempotent on re-entry: a crash between them leaves an unresolved entry, so the
next tick observes it again, finds the node already blocked, and finishes the
sequence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from amoeba.process import RunOutcome
from amoeba.runner.faults import ResumeFailure
from amoeba.runner.ingest.outcome import PAYLOAD_REASON, PAYLOAD_RUN_ID, BlockPlan
from amoeba.runner.ingest.record import (
    RESULT_OUTCOME,
    RESULT_OUTCOME_DOCUMENT,
    RESULT_RUN_ID,
    block_once,
    entry_run_id,
    ingest,
)
from amoeba.runner.observed import (
    Finished,
    LaunchFailed,
    ResumeFailed,
    RunEnded,
    RunVanished,
)
from amoeba.runner.resolutions.vocabulary import REASON_RESUME_FAILED

if TYPE_CHECKING:
    from amoeba.runner.gates.outcome import OutcomeObservation
from amoeba.store import (
    BlockedKind,
    JournalEntry,
    JournalOutcome,
    Store,
)

#: Result and payload keys of a failed launch.
RESULT_LAUNCH_FAILURE: Final = "launch_failure"
#: The result key of a failed resume (slice 127, D6), beside the launch's.
RESULT_RESUME_FAILURE: Final = "resume_failure"
PAYLOAD_EXIT_CODE: Final = "exit_code"
PAYLOAD_STDERR_TAIL: Final = "stderr_tail"


def record(
    store: Store,
    entry: JournalEntry,
    finished: Finished,
    version_label: str,
    observation: OutcomeObservation | None = None,
) -> None:
    """Block the entry's node when a human must look, then resolve the entry.

    ``version_label`` is the ``sq --version`` label captured once at start-up; it
    labels a recorded review whose file carries no stamp of its own. ``observation``
    is the outcome observation a ``completed`` run needs (slice 128, D2).
    """
    match finished:
        case RunEnded() | RunVanished():
            ingest(store, entry, finished, version_label, observation)
        case LaunchFailed():
            _record_launch_failed(store, entry, finished)
        case ResumeFailed():
            _record_resume_failed(store, entry, finished)


def _record_launch_failed(
    store: Store, entry: JournalEntry, finished: LaunchFailed
) -> None:
    run_id = entry_run_id(entry)
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


def _record_resume_failed(
    store: Store, entry: JournalEntry, finished: ResumeFailed
) -> None:
    """Block on a human, then resolve ``failed`` keeping the run's real outcome.

    The run is still paused, with its branch checked out, so the result says
    ``paused`` and carries the last poll: the checkout stays held and the situation
    stays ``paused_run``. A run that is gone says ``not_found``, which releases both
    (D6).
    """
    run_id = entry_run_id(entry)
    code = "unknown" if finished.exit_code is None else str(finished.exit_code)
    context = (
        f"resume of {run_id} failed ({finished.failure.value}); "
        f"exit code {code}; stderr: {finished.tail}"
    )
    payload: dict[str, object] = {
        PAYLOAD_REASON: REASON_RESUME_FAILED,
        RESULT_RESUME_FAILURE: finished.failure.value,
        PAYLOAD_RUN_ID: run_id,
        PAYLOAD_EXIT_CODE: finished.exit_code,
        PAYLOAD_STDERR_TAIL: finished.tail,
    }
    block_once(store, entry.node_id, BlockPlan(BlockedKind.HUMAN, context, payload))
    missing = finished.failure is ResumeFailure.RUN_MISSING
    outcome = RunOutcome.NOT_FOUND if missing else RunOutcome.PAUSED
    document = finished.document
    store.journal_resolve(
        entry.id,
        outcome=JournalOutcome.FAILED,
        result={
            RESULT_RUN_ID: run_id,
            RESULT_OUTCOME: outcome.value,
            RESULT_OUTCOME_DOCUMENT: (
                None if document is None else document.model_dump(mode="json")
            ),
            RESULT_RESUME_FAILURE: finished.failure.value,
        },
    )
