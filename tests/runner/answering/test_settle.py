"""``settle_pending``: one case per branch, and the order of the checks (D5)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from amoeba.runner.answering import settle
from amoeba.runner.answering.settle import (
    Decline,
    Launch,
    QuestionInvariantError,
    Skip,
    settle_pending,
)
from amoeba.store import (
    BlockedKind,
    BlockedState,
    DeclineReason,
    QuestionRecord,
    QuestionState,
    Resolution,
)
from runner.purity import io_use

STAMP = datetime(2026, 11, 2, tzinfo=UTC)


def _record(question: str | None = "which branch?") -> QuestionRecord:
    return QuestionRecord(
        id="q-1",
        project_id="demo",
        node_id="n-1",
        source_entry_id="e-1",
        run_id="run-1",
        step="implement",
        question=question,
        truncated=False,
        blocked_state_id="b-1",
        state=QuestionState.PENDING,
        answered_by=None,
        answer=None,
        decline_reason=None,
        created_at=STAMP,
        updated_at=STAMP,
        reserved_term=None,
        answering_entry_id=None,
        source_commit=None,
        passage_index=None,
        dropped_pm_answers=None,
        proposed_answer=None,
        cited_passages=None,
        check_verdict=None,
        check_reason=None,
        decline_detail=None,
    )


def _block(*, resolved: bool = False, awaits_runner: bool = False) -> BlockedState:
    return BlockedState(
        id="b-1",
        node_id="n-1",
        kind=BlockedKind.HUMAN,
        context="ctx",
        resolution=Resolution("pm", "go") if resolved else None,
        awaits_runner=awaits_runner,
    )


def test_an_open_block_with_no_answerer_section_is_declined_not_configured() -> None:
    assert settle_pending(_record(), _block(), configured=False) == Decline(
        DeclineReason.ANSWERER_NOT_CONFIGURED
    )


def test_an_open_block_with_the_section_present_is_launched() -> None:
    assert settle_pending(_record(), _block(), configured=True) == Launch()


@pytest.mark.parametrize("question", [None, ""])
def test_a_null_or_empty_question_is_declined_missing(question: str | None) -> None:
    result = settle_pending(_record(question), _block(), configured=True)

    assert result == Decline(DeclineReason.QUESTION_MISSING)


def test_a_resolved_block_awaiting_the_runner_is_skipped() -> None:
    result = settle_pending(
        _record(), _block(resolved=True, awaits_runner=True), configured=True
    )

    assert result == Skip()


def test_a_resolved_block_awaiting_the_runner_with_a_null_question_is_skipped() -> None:
    result = settle_pending(
        _record(None), _block(resolved=True, awaits_runner=True), configured=False
    )

    assert result == Skip()


def test_a_resolved_block_not_awaiting_the_runner_raises() -> None:
    with pytest.raises(QuestionInvariantError):
        settle_pending(_record(), _block(resolved=True), configured=True)


def test_the_invariant_raises_even_when_the_question_is_null() -> None:
    with pytest.raises(QuestionInvariantError):
        settle_pending(_record(None), _block(resolved=True), configured=False)


def test_settle_does_no_io() -> None:
    assert io_use(settle) == []
