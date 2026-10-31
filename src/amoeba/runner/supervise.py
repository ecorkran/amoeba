"""The supervisor's rules: what a finished run means, and how long to keep resuming.

Pure: no store, no I/O, no clock. Squadron owns the pipeline; Amoeba only decides
whether a run is done, can be resumed, needs an answer, or needs a person (slice 132,
D4 and D5). This is the one module that names an outcome class, a payload reason or
a transient failure kind.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Final

from pydantic import ValidationError

from amoeba.process import (
    CheckpointKind,
    FailureKind,
    RunOutcome,
    RunOutcomeDocument,
    parse_checkpoint_kind,
    parse_failure_kind,
)
from amoeba.runner.observed import Finished, RunEnded
from amoeba.runner.resolutions.vocabulary import PARAM_RESUME_CAUSE, ResumeCause
from amoeba.store import CommandKind, JournalEntry

#: The key of a resolved ``sq_run`` entry's result that holds the outcome document it
#: was resolved with: the supervisor's record of where the run stopped (D4).
RESULT_OUTCOME_DOCUMENT: Final = "outcome_document"
#: The key that holds the run outcome's name (``paused``, ``failed``, ...), kept apart
#: from the document so a failed resume can record that the run is gone.
RESULT_OUTCOME: Final = "outcome"

#: The recorded outcomes of a run Squadron still has and can resume.
RESUMABLE_OUTCOMES: Final = frozenset(
    {RunOutcome.PAUSED.value, RunOutcome.FAILED.value, RunOutcome.ORPHANED.value}
)

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


def step_of(document: RunOutcomeDocument) -> str | None:
    """The pipeline step a run stopped at: the checkpoint's, else the failure's."""
    if document.checkpoint and document.checkpoint.step:
        return document.checkpoint.step
    if document.failure and document.failure.step:
        return document.failure.step
    return None


def recorded_document(entry: JournalEntry) -> RunOutcomeDocument | None:
    """The outcome document a resolved entry holds, or ``None`` if it holds none.

    A missing or unparsable document is unknown, never an error.
    """
    raw = None if entry.result is None else entry.result.get(RESULT_OUTCOME_DOCUMENT)
    if not isinstance(raw, dict):
        return None
    try:
        return RunOutcomeDocument.model_validate(raw)
    except ValidationError:
        # A stored document that no longer fits the model is unknown, not a fault.
        return None


def resume_count(entries: Sequence[JournalEntry], step: str | None) -> int:
    """How many automatic resumes of one run have already stopped at ``step`` (D5).

    ``entries`` are the slice's ``sq_run`` entries, newest first, starting with the
    entry whose outcome is being ingested. It counts the trailing entries that are
    transient resumes of an outcome that stopped at ``step``; a fresh launch, a
    resolution resume or a different step ends the count. An observation (a resume
    skipped because the run had moved on) carries the cause too and counts: a run that
    then stops again is nearer its limit, which errs toward blocking, never toward
    spending. A ``step`` of ``None``
    (an orphaned run reports none) is the step the newest entry resumed from.
    """
    if step is None:
        step = _stopped_step(entries, 1)
    count = 0
    for index, entry in enumerate(entries):
        if entry.parameters.get(PARAM_RESUME_CAUSE) != ResumeCause.TRANSIENT:
            break
        if _stopped_step(entries, index + 1) != step:
            break
        count += 1
    return count


def _stopped_step(entries: Sequence[JournalEntry], index: int) -> str | None:
    """The step the outcome of ``entries[index]`` stopped at.

    An orphaned outcome reports no step and counts as the step of the entry before it.
    """
    while index < len(entries):
        document = recorded_document(entries[index])
        if document is None:
            return None
        step = step_of(document)
        if step is not None or document.outcome is not RunOutcome.ORPHANED:
            return step
        index += 1
    return None


def resume_ready(document: RunOutcomeDocument, now: datetime) -> bool:
    """Whether a resume may be issued now (D5, "When").

    True for every ``TRANSIENT`` outcome except a ``usage_limit`` pause before its
    ``resets_at``. Any other class is never resumed automatically.
    """
    if classify(RunEnded(document)) is not OutcomeClass.TRANSIENT:
        return False
    checkpoint = document.checkpoint
    if document.outcome is RunOutcome.PAUSED and checkpoint and checkpoint.resets_at:
        return now >= checkpoint.resets_at
    return True


def run_to_resume(entries: Sequence[JournalEntry]) -> JournalEntry | None:
    """The run entry a ``resume`` resolution would resume, or ``None``.

    ``entries`` are the slice's, oldest first. It is the latest entry, when that is a
    resolved ``sq_run`` whose recorded outcome is one Squadron can resume. A failed
    launch, a vanished run and a run whose resume found it gone give ``None``: there
    is no run to resume (D6).
    """
    latest = entries[-1] if entries else None
    if (
        latest is None
        or latest.kind is not CommandKind.SQ_RUN
        or not latest.is_resolved
    ):
        return None
    recorded = None if latest.result is None else latest.result.get(RESULT_OUTCOME)
    return latest if recorded in RESUMABLE_OUTCOMES else None
