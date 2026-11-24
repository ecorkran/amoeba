"""One definition of what Amoeba does with a pause (slice 224, D3).

``handle_pause`` and ``status`` both ask :func:`classify_pause`, so a pause that
``status`` calls a missed hook is one ``handle_pause`` picks up. The function is pure:
it reads no file, store or process, and takes the run file's facts as a value. The
callers read ``run_facts`` only when :func:`run_facts_needed` says the answer depends
on them.
"""

from __future__ import annotations

from amoeba.operations.pause_observed import (
    ObservedPause,
    PauseClass,
    classify_run_only,
)
from amoeba.store.models import AnswerRecord, QuestionRecord
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from amoeba.upstream.squadron.run_file import ExecutionMode, RunFacts
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument

#: Resume outcomes after which the answer needs no further delivery.
DELIVERED: frozenset[ResumeOutcome] = frozenset(
    {ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED}
)


def observed_from_document(document: RunOutcomeDocument) -> ObservedPause:
    """The pause of a ``sq runs wait --json`` document."""
    checkpoint = document.checkpoint
    return ObservedPause(
        paused=document.outcome is RunOutcome.PAUSED,
        kind=None if checkpoint is None else checkpoint.kind,
        paused_at=None if checkpoint is None else checkpoint.paused_at_text,
        question=None if checkpoint is None else checkpoint.question,
    )


def run_facts_needed(
    observed: ObservedPause, question_row: QuestionRecord | None
) -> bool:
    """Whether :func:`classify_pause` needs ``run_facts``: only for a paused agent
    question with text that has no row yet."""
    return classify_run_only(observed) is None and question_row is None


def classify_no_row(run_facts: RunFacts) -> PauseClass:
    """A paused agent question nothing has recorded: its agent's, or a missed hook."""
    if run_facts.execution_mode is ExecutionMode.PROMPT_ONLY:
        return PauseClass.PROMPT_ONLY
    return PauseClass.UNHANDLED


def classify_pause(  # noqa: PLR0913 - the D3 table's inputs, each a value
    observed: ObservedPause,
    question_row: QuestionRecord | None,
    latest_answer: AnswerRecord | None,
    run_facts: RunFacts | None,
    claim_stale: bool,
) -> PauseClass:
    """The D3 class of a pause.

    ``claim_stale`` is the hub's judgment (``claim_is_stale``) of a ``claimed`` row's
    age against ``pause_claim_seconds``; it is ignored for any other state.
    ``latest_answer`` is the question's newest answer, required for an ``answered``
    row.

    Raises:
        ValueError: ``run_facts`` is missing where :func:`run_facts_needed` is true,
            or an ``answered`` row came without its answer. Both are caller bugs.
    """
    early = classify_run_only(observed)
    if early is not None:
        return early
    if question_row is None:
        if run_facts is None:
            raise ValueError("a pause with no row needs run_facts")
        return classify_no_row(run_facts)
    match question_row.state:
        case QuestionState.WAITING_ON_PM:
            return PauseClass.WAITING_ON_PM
        case QuestionState.WAITING_ON_REQUEST:
            return PauseClass.WAITING_ON_REQUEST
        case QuestionState.CLAIMED:
            return PauseClass.CLAIM_STALE if claim_stale else PauseClass.CLAIM_LIVE
        case QuestionState.CLOSED:
            return PauseClass.CLOSED
        case QuestionState.ANSWERED:
            if latest_answer is None:
                raise ValueError("an answered question needs its latest answer")
            if latest_answer.resume_outcome in DELIVERED:
                return PauseClass.SETTLED
            return PauseClass.ANSWERED_UNRESUMED
