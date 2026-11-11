"""Every ``PauseClass``, built from the D3 table's "When" column (slice 224, 1.1)."""

from __future__ import annotations

import pytest

from amoeba.operations.pause_class import (
    ObservedPause,
    PauseClass,
    classify_pause,
    run_facts_needed,
)
from amoeba.store.models import AnswerRecord, QuestionKey, QuestionRecord
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from amoeba.upstream.squadron.run_file import ExecutionMode, RunFacts
from operations.status_support import RUN_NOW, answer_row, question_row

NOW = RUN_NOW
LIMIT = 600.0
KEY = QuestionKey("run-1", "2026-11-11T11:00:00+00:00")
SDK = RunFacts(params={}, execution_mode=ExecutionMode.SDK)
PROMPT_ONLY = RunFacts(params={}, execution_mode=ExecutionMode.PROMPT_ONLY)
ASKING = ObservedPause(
    paused=True, kind="agent_question", paused_at=KEY.paused_at, question="Which?"
)


def _row(state: QuestionState, *, age_seconds: float = 0.0) -> QuestionRecord:
    return question_row(KEY, state, age_seconds=age_seconds)


def _answer(outcome: ResumeOutcome | None) -> AnswerRecord:
    return answer_row(KEY, outcome)


def _classify(
    observed: ObservedPause = ASKING,
    row: QuestionRecord | None = None,
    latest: AnswerRecord | None = None,
    facts: RunFacts | None = None,
) -> PauseClass:
    return classify_pause(observed, row, latest, facts, LIMIT, NOW)


def test_a_run_that_is_not_paused_is_not_paused() -> None:
    running = ObservedPause(paused=False, kind=None, paused_at=None, question=None)

    assert _classify(running) is PauseClass.NOT_PAUSED


@pytest.mark.parametrize("kind", ["interactive_checkpoint", "usage_limit", "new_kind"])
def test_another_checkpoint_kind_is_other_checkpoint(kind: str) -> None:
    other = ObservedPause(True, kind, KEY.paused_at, "Which?")

    assert _classify(other) is PauseClass.OTHER_CHECKPOINT


def test_a_paused_run_with_no_checkpoint_is_other_checkpoint() -> None:
    bare = ObservedPause(paused=True, kind=None, paused_at=None, question=None)

    assert _classify(bare) is PauseClass.OTHER_CHECKPOINT


@pytest.mark.parametrize(
    ("paused_at", "question"),
    [(KEY.paused_at, None), (KEY.paused_at, "  "), (None, "Which?")],
)
def test_an_agent_question_without_text_or_time_has_no_question_text(
    paused_at: str | None, question: str | None
) -> None:
    broken = ObservedPause(True, "agent_question", paused_at, question)

    assert _classify(broken) is PauseClass.NO_QUESTION_TEXT


def test_no_row_and_a_prompt_only_run_is_prompt_only() -> None:
    assert _classify(facts=PROMPT_ONLY) is PauseClass.PROMPT_ONLY


def test_no_row_and_an_sdk_run_is_unhandled() -> None:
    assert _classify(facts=SDK) is PauseClass.UNHANDLED


def test_no_row_without_run_facts_is_a_caller_bug() -> None:
    with pytest.raises(ValueError, match="run_facts"):
        _classify()


def test_a_young_claim_is_live() -> None:
    assert _classify(row=_row(QuestionState.CLAIMED, age_seconds=1)) is (
        PauseClass.CLAIM_LIVE
    )


def test_a_claim_exactly_at_the_limit_is_stale() -> None:
    row = _row(QuestionState.CLAIMED, age_seconds=LIMIT)

    assert _classify(row=row) is PauseClass.CLAIM_STALE


def test_a_claim_just_under_the_limit_is_live() -> None:
    row = _row(QuestionState.CLAIMED, age_seconds=LIMIT - 0.001)

    assert _classify(row=row) is PauseClass.CLAIM_LIVE


def test_a_waiting_row_is_waiting_on_the_pm() -> None:
    assert _classify(row=_row(QuestionState.WAITING_ON_PM)) is (
        PauseClass.WAITING_ON_PM
    )


@pytest.mark.parametrize("outcome", [None, ResumeOutcome.REFUSED])
def test_an_answer_not_handed_over_is_answered_unresumed(
    outcome: ResumeOutcome | None,
) -> None:
    result = _classify(row=_row(QuestionState.ANSWERED), latest=_answer(outcome))

    assert result is PauseClass.ANSWERED_UNRESUMED


@pytest.mark.parametrize(
    "outcome", [ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED]
)
def test_a_handed_over_answer_is_settled(outcome: ResumeOutcome) -> None:
    result = _classify(row=_row(QuestionState.ANSWERED), latest=_answer(outcome))

    assert result is PauseClass.SETTLED


def test_an_answered_row_without_its_answer_is_a_caller_bug() -> None:
    with pytest.raises(ValueError, match="latest answer"):
        _classify(row=_row(QuestionState.ANSWERED))


def test_a_row_decides_the_class_whatever_the_run_file_says() -> None:
    row = _row(QuestionState.WAITING_ON_PM)

    assert _classify(row=row, facts=PROMPT_ONLY) is PauseClass.WAITING_ON_PM


def test_run_facts_are_needed_only_for_an_agent_question_with_no_row() -> None:
    not_paused = ObservedPause(False, None, None, None)
    textless = ObservedPause(True, "agent_question", None, None)

    assert run_facts_needed(ASKING, None)
    assert not run_facts_needed(ASKING, _row(QuestionState.CLAIMED))
    assert not run_facts_needed(not_paused, None)
    assert not run_facts_needed(textless, None)
