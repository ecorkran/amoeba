"""Finish an answering run: settle the question, then resolve the journal entry (D9).

The order is the crash safety. The record is settled first, in one store call that
is idempotent on re-entry (a record that is no longer ``answering`` is not written
again), and the entry is resolved last. A crash between them leaves an unresolved
entry, which the next tick observes again and finishes without a second submission
or decline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from pathlib import Path
from typing import Final

from amoeba.runner.answering.artifacts import (
    AnswerReply,
    ArtifactProblem,
    CheckReply,
    read_answer,
    read_check,
)
from amoeba.runner.answering.decide import (
    Confirmed,
    Declined,
    RunState,
    RunSummary,
    decide_answer,
)
from amoeba.runner.answering.gate import compose_instructions, evaluate_gate
from amoeba.runner.answering.settle import QuestionInvariantError
from amoeba.runner.observed import Finished
from amoeba.runner.project_config import AnswererSettings
from amoeba.store import (
    PARAM_RUN_ID,
    PARAM_SCRATCH,
    AnsweredBy,
    AnsweringEvidence,
    AnswerOutcome,
    JournalEntry,
    JournalOutcome,
    QuestionRecord,
    QuestionState,
    Store,
)

#: The detail the resolution the answerer submits carries.
ANSWERER_DETAIL: Final = "answered by the question answerer"

#: Keys of the entry's result.
RESULT_RUN_ID: Final = "run_id"
RESULT_RUN_OUTCOME: Final = "run_outcome"
RESULT_DECISION: Final = "decision"
RESULT_QUESTION_OUTCOME: Final = "question_outcome"

#: The result's ``decision`` for an answer that passed every check.
DECISION_CONFIRMED: Final = "confirmed"


class QuestionOutcome(StrEnum):
    """What became of the question when its run was finished."""

    SUBMITTED = "submitted"
    DECLINED = "declined"
    BLOCK_RESOLVED = "block_resolved"
    SETTLED = "settled"
    #: The record was no longer waiting on this run (the PM answered first).
    DISCARDED = "discarded"


@dataclass(frozen=True)
class Settlement:
    """How a finished run left its question: the outcome and the decision behind it."""

    question_outcome: QuestionOutcome
    #: ``confirmed``, or the decline reason's value; ``None`` when discarded.
    decision: str | None


_SUBMISSION_OUTCOMES: Final = {
    AnswerOutcome.SUBMITTED: QuestionOutcome.SUBMITTED,
    AnswerOutcome.DECLINED: QuestionOutcome.DECLINED,
    AnswerOutcome.BLOCK_RESOLVED: QuestionOutcome.BLOCK_RESOLVED,
    AnswerOutcome.SETTLED: QuestionOutcome.SETTLED,
}


def settle_run_result(
    store: Store,
    record: QuestionRecord,
    entry: JournalEntry,
    finished: Finished,
    settings: AnswererSettings,
) -> Settlement:
    """Apply a finished run to its question, and say what happened.

    A record that is not ``answering`` for this entry is left alone: ``discarded``
    when someone else answered it, or the earlier outcome again when an earlier
    attempt at this very finish already wrote it.
    """
    if record.state is not QuestionState.ANSWERING or (
        record.answering_entry_id != entry.id
    ):
        return _already_settled(record, entry)
    run = RunSummary.of(finished)
    answer, check = _read_replies(run, entry)
    decided = decide_answer(run, answer, check, _passage_ids(record))
    if isinstance(decided, Confirmed):
        return _submit(store, record, decided, settings)
    return _decline(store, record, decided)


def _already_settled(record: QuestionRecord, entry: JournalEntry) -> Settlement:
    """The outcome an earlier attempt at this finish left, or ``discarded``."""
    if record.answering_entry_id == entry.id:
        if (
            record.state is QuestionState.ANSWERED
            and record.answered_by is AnsweredBy.ANSWERER
        ):
            return Settlement(QuestionOutcome.SUBMITTED, DECISION_CONFIRMED)
        if record.state is QuestionState.DECLINED and record.decline_reason:
            return Settlement(QuestionOutcome.DECLINED, record.decline_reason.value)
    return Settlement(QuestionOutcome.DISCARDED, None)


def _read_replies(
    run: RunSummary, entry: JournalEntry
) -> tuple[AnswerReply | ArtifactProblem | None, CheckReply | ArtifactProblem | None]:
    """The two reply files, read only when the run completed; else ``None``s."""
    if run.state is not RunState.COMPLETED:
        return None, None
    scratch = entry.parameters.get(PARAM_SCRATCH)
    if not isinstance(scratch, str):
        raise ValueError(f"entry {entry.id} has an unusable scratch: {scratch!r}")
    directory = Path(scratch)
    return read_answer(directory), read_check(directory)


def _passage_ids(record: QuestionRecord) -> frozenset[str]:
    if record.passage_index is None:
        raise QuestionInvariantError(
            f"answering question {record.id!r} has no recorded passage index"
        )
    return frozenset(passage.id for passage in record.passage_index)


def _submit(
    store: Store, record: QuestionRecord, decided: Confirmed, settings: AnswererSettings
) -> Settlement:
    if record.question is None:
        raise QuestionInvariantError(f"question {record.id!r} has no question text")
    submission = store.submit_answer(
        record.id,
        answer=decided.answer,
        instructions=compose_instructions(record.question, decided.answer),
        detail=ANSWERER_DETAIL,
        gate=partial(evaluate_gate, answer=decided.answer, settings=settings),
        evidence=decided.evidence,
    )
    outcome = _SUBMISSION_OUTCOMES[submission.outcome]
    if outcome is QuestionOutcome.DECLINED and submission.record.decline_reason:
        return Settlement(outcome, submission.record.decline_reason.value)
    return Settlement(outcome, DECISION_CONFIRMED)


def _decline(store: Store, record: QuestionRecord, decided: Declined) -> Settlement:
    store.decline_question(
        record.id,
        reason=decided.reason,
        detail=decided.detail,
        evidence=_evidence_or_none(decided.evidence),
    )
    return Settlement(QuestionOutcome.DECLINED, decided.reason.value)


def _evidence_or_none(evidence: AnsweringEvidence) -> AnsweringEvidence | None:
    return None if evidence == AnsweringEvidence() else evidence


def finish_answering(
    store: Store,
    entry: JournalEntry,
    finished: Finished,
    settings: AnswererSettings,
) -> Settlement:
    """Settle the entry's question, then resolve the entry with what happened."""
    record = store.question_for_answering_entry(entry.id)
    if record is None:
        settlement = Settlement(QuestionOutcome.DISCARDED, None)
    else:
        settlement = settle_run_result(store, record, entry, finished, settings)
    run = RunSummary.of(finished)
    completed = run.state is RunState.COMPLETED
    store.journal_resolve(
        entry.id,
        outcome=JournalOutcome.COMPLETED if completed else JournalOutcome.FAILED,
        result={
            RESULT_RUN_ID: entry.parameters[PARAM_RUN_ID],
            RESULT_RUN_OUTCOME: run.state.value,
            RESULT_DECISION: settlement.decision,
            RESULT_QUESTION_OUTCOME: settlement.question_outcome.value,
        },
    )
    return settlement
