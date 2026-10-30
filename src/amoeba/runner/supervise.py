"""The supervisor's rules: what a finished run means, and how long to keep resuming.

Pure: no store, no I/O, no clock. Squadron owns the pipeline; Amoeba only decides
whether a run is done, can be resumed, needs an answer, or needs a person (slice 132,
D4 and D5). This is the one module that names an outcome class, a payload reason or
a transient failure kind.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from amoeba.process import (
    CheckpointKind,
    FailureKind,
    RunOutcome,
    RunOutcomeDocument,
    parse_checkpoint_kind,
    parse_failure_kind,
)
from amoeba.runner.observed import Finished, RunEnded

#: The ``reason`` a block payload carries (D4). ``agent_question`` is 140's input.
REASON_AGENT_QUESTION: Final = "agent_question"
REASON_PAUSED: Final = "paused"
REASON_FAILED: Final = "failed"
REASON_AUTO_RESUME_EXHAUSTED: Final = "auto_resume_exhausted"

#: Failures Squadron resumes through; every other failure kind needs a person.
TRANSIENT_FAILURE_KINDS: Final = frozenset(
    {FailureKind.PROVIDER_ERROR, FailureKind.STALL}
)


class OutcomeClass(StrEnum):
    """What a finished run means to the supervisor. Closed: nothing else is added."""

    #: The pipeline finished; the slice is done.
    COMPLETED = "completed"
    #: Resume it, within the bound (D5).
    TRANSIENT = "transient"
    #: The agent asked a question; 140 answers it.
    QUESTION = "question"
    #: A person has to look.
    BLOCKED = "blocked"


def classify(observed: Finished) -> OutcomeClass:
    """The class of a run that ended, was found gone, or never started or resumed.

    Raises:
        ValueError: The document's outcome is not an end state (``timed_out`` is a
            run still going; the others are faults the tick handles).
    """
    if not isinstance(observed, RunEnded):
        # Vanished, launch failed and resume failed all need a person (D4).
        return OutcomeClass.BLOCKED
    document = observed.document
    match document.outcome:
        case RunOutcome.COMPLETED:
            return OutcomeClass.COMPLETED
        case RunOutcome.ORPHANED:
            return OutcomeClass.TRANSIENT
        case RunOutcome.FAILED:
            return _classify_failure(
                document.failure.kind if document.failure else None
            )
        case RunOutcome.PAUSED:
            return _classify_pause(document)
        case _:
            raise ValueError(
                f"run {document.run_id} outcome {document.outcome.value} "
                "is not an end state"
            )


def _classify_failure(kind: str | None) -> OutcomeClass:
    if parse_failure_kind(kind) in TRANSIENT_FAILURE_KINDS:
        return OutcomeClass.TRANSIENT
    return OutcomeClass.BLOCKED


def _classify_pause(document: RunOutcomeDocument) -> OutcomeClass:
    checkpoint = document.checkpoint
    kind = parse_checkpoint_kind(checkpoint.kind if checkpoint else None)
    if kind is CheckpointKind.AGENT_QUESTION:
        return OutcomeClass.QUESTION
    # A usage limit without a reset time is never resumed blind (D5).
    if kind is CheckpointKind.USAGE_LIMIT and checkpoint and checkpoint.resets_at:
        return OutcomeClass.TRANSIENT
    return OutcomeClass.BLOCKED
