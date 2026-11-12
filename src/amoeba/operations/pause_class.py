"""One definition of what Amoeba does with a pause (slice 224, D3).

``handle_pause`` and ``status`` both ask :func:`classify_pause`, so a pause that
``status`` calls a missed hook is one ``handle_pause`` picks up. The function is pure:
it reads no file, store or process, and takes the run file's facts as a value. The
callers read ``run_facts`` only when :func:`run_facts_needed` says the answer depends
on them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from amoeba.store.models import AnswerRecord, QuestionRecord
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from amoeba.upstream.squadron.run_file import ExecutionMode, RunFacts
from amoeba.upstream.squadron.run_outcome import (
    CheckpointKind,
    RunOutcome,
    RunOutcomeDocument,
    parse_checkpoint_kind,
)


class PauseClass(StrEnum):
    """What a run's pause is, in the D3 table's order."""

    NOT_PAUSED = "not_paused"
    OTHER_CHECKPOINT = "other_checkpoint"
    NO_QUESTION_TEXT = "no_question_text"
    PROMPT_ONLY = "prompt_only"
    UNHANDLED = "unhandled"
    CLAIM_LIVE = "claim_live"
    CLAIM_STALE = "claim_stale"
    WAITING_ON_PM = "waiting_on_pm"
    ANSWERED_UNRESUMED = "answered_unresumed"
    SETTLED = "settled"


#: Resume outcomes after which the answer needs no further delivery.
DELIVERED: frozenset[ResumeOutcome] = frozenset(
    {ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED}
)


@dataclass(frozen=True)
class ObservedPause:
    """What Squadron says about a run, in the terms both callers can give.

    ``sq runs wait`` and ``sq runs list`` report a run differently (an outcome and a
    status string); each caller reduces its report to this.
    """

    #: Whether the run is paused.
    paused: bool
    #: The checkpoint's kind, raw as Squadron printed it.
    kind: str | None
    #: The checkpoint's ``paused_at`` as ``sq runs wait --json`` prints it.
    paused_at: str | None
    question: str | None


def observed_from_document(document: RunOutcomeDocument) -> ObservedPause:
    """The pause of a ``sq runs wait --json`` document."""
    checkpoint = document.checkpoint
    return ObservedPause(
        paused=document.outcome is RunOutcome.PAUSED,
        kind=None if checkpoint is None else checkpoint.kind,
        paused_at=None if checkpoint is None else checkpoint.paused_at_text,
        question=None if checkpoint is None else checkpoint.question,
    )


def classify_run_only(observed: ObservedPause) -> PauseClass | None:
    """The first three classes, which need nothing but the run; ``None`` if the run
    is a paused agent question with text, whose class depends on the rest."""
    if not observed.paused:
        return PauseClass.NOT_PAUSED
    if parse_checkpoint_kind(observed.kind) is not CheckpointKind.AGENT_QUESTION:
        return PauseClass.OTHER_CHECKPOINT
    if observed.paused_at is None or not (observed.question or "").strip():
        return PauseClass.NO_QUESTION_TEXT
    return None


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
    claim_age_limit: float,
    now: datetime,
) -> PauseClass:
    """The D3 class of a pause.

    ``claim_age_limit`` is ``answering_wait_seconds``; a claim as old as the limit is
    stale. ``latest_answer`` is the question's newest answer, required for an
    ``answered`` row.

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
        case QuestionState.CLAIMED:
            age = now - question_row.updated_at
            if age >= timedelta(seconds=claim_age_limit):
                return PauseClass.CLAIM_STALE
            return PauseClass.CLAIM_LIVE
        case QuestionState.ANSWERED:
            if latest_answer is None:
                raise ValueError("an answered question needs its latest answer")
            if latest_answer.resume_outcome in DELIVERED:
                return PauseClass.SETTLED
            return PauseClass.ANSWERED_UNRESUMED
