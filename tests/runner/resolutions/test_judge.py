"""``judge_resolution``: every check and every row, as answers (D6)."""

from __future__ import annotations

import pytest

from amoeba.runner.resolutions.judge import Acknowledgment, judge_resolution
from amoeba.runner.resolutions.vocabulary import (
    ALLOWED,
    PAYLOAD_ALLOWED,
    PAYLOAD_CODE,
    PAYLOAD_DETAIL,
    PAYLOAD_REJECTED_BLOCKED_STATE_ID,
    PAYLOAD_STOPPED_BLOCKED_STATE_ID,
    REASON_RESOLUTION_REJECTED,
    REASON_STOPPED,
    Situation,
)
from amoeba.store import (
    BlockedKind,
    BlockedState,
    BlockEffect,
    Resolution,
    ResolutionOutcome,
)

RUN = Situation.RUN_TO_RESUME
NO_RUN = Situation.NO_RUN


def _blocked(
    decision: str | None = None, instructions: str | None = None
) -> BlockedState:
    return BlockedState(
        id="b-1",
        node_id="n-1",
        kind=BlockedKind.HUMAN,
        context="decide",
        resolution=Resolution(
            resolved_by="pm",
            detail="go",
            decision=decision,
            instructions=instructions,
        ),
    )


def _rejection(answer: Acknowledgment) -> str:
    assert answer.outcome is ResolutionOutcome.REJECTED
    assert answer.code is not None
    assert isinstance(answer.effect, BlockEffect)
    return answer.code


@pytest.mark.parametrize(
    ("decision", "instructions", "situation", "code"),
    [
        ("resume", None, Situation.UNRESOLVABLE, "unresolvable"),
        (None, None, Situation.UNRESOLVABLE, "unresolvable"),
        ("maybe", None, RUN, "unknown_decision"),
        ("retry", None, RUN, "unknown_decision"),
        ("accept", None, RUN, "unknown_decision"),
        ("handled", None, RUN, "unknown_decision"),
        ("rerun", None, NO_RUN, "unknown_decision"),
        (None, None, RUN, "decision_required"),
        (None, None, NO_RUN, "decision_required"),
        ("resume", "do it", NO_RUN, "instructions_not_applicable"),
        ("stop", "do it", RUN, "instructions_not_applicable"),
        ("stop", "do it", NO_RUN, "instructions_not_applicable"),
    ],
)
def test_each_check_rejects_with_its_code(
    decision: str | None,
    instructions: str | None,
    situation: Situation,
    code: str,
) -> None:
    answer = judge_resolution(_blocked(decision, instructions), situation)

    assert _rejection(answer) == code


def test_the_first_failing_check_wins() -> None:
    unresolvable = judge_resolution(_blocked("maybe"), Situation.UNRESOLVABLE)

    assert _rejection(unresolvable) == "unresolvable"


def test_a_rejection_blocks_again_and_lists_what_is_allowed() -> None:
    answer = judge_resolution(_blocked("accept"), RUN)

    assert answer.reason is not None
    effect = answer.effect
    assert isinstance(effect, BlockEffect)
    assert effect.context == "resolution rejected: unknown_decision"
    assert effect.payload == {
        "reason": REASON_RESOLUTION_REJECTED,
        PAYLOAD_CODE: "unknown_decision",
        PAYLOAD_DETAIL: answer.reason,
        PAYLOAD_REJECTED_BLOCKED_STATE_ID: "b-1",
        PAYLOAD_ALLOWED: sorted(d.value for d in ALLOWED[RUN]),
    }


@pytest.mark.parametrize(
    ("decision", "instructions", "situation"),
    [
        ("resume", None, RUN),
        ("resume", "narrow it", RUN),
        ("resume", None, NO_RUN),
    ],
)
def test_a_resume_is_applied_with_no_effect(
    decision: str, instructions: str | None, situation: Situation
) -> None:
    answer = judge_resolution(_blocked(decision, instructions), situation)

    assert answer == Acknowledgment(ResolutionOutcome.APPLIED, None, None, None)


@pytest.mark.parametrize("situation", [RUN, NO_RUN])
def test_stop_parks_the_node_as_a_block(situation: Situation) -> None:
    answer = judge_resolution(_blocked("stop"), situation)

    assert answer.outcome is ResolutionOutcome.APPLIED
    assert answer.effect == BlockEffect(
        context="stopped by pm",
        payload={"reason": REASON_STOPPED, PAYLOAD_STOPPED_BLOCKED_STATE_ID: "b-1"},
    )


def test_an_unresolved_state_is_a_programming_error() -> None:
    unresolved = BlockedState(id="b", node_id="n", kind=BlockedKind.HUMAN, context="c")

    with pytest.raises(ValueError, match="not resolved"):
        judge_resolution(unresolved, RUN)
