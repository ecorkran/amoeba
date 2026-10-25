"""``judge_resolution``: every D2 check and every D3 row, as answers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from amoeba.process import RunCheckpoint
from amoeba.runner.ingest.record import RESULT_OUTCOME_DOCUMENT
from amoeba.runner.resolutions.judge import (
    Acknowledgment,
    checkpoint_of,
    judge_resolution,
)
from amoeba.runner.resolutions.vocabulary import (
    ALLOWED,
    PAYLOAD_ALLOWED,
    PAYLOAD_CODE,
    PAYLOAD_DETAIL,
    PAYLOAD_REJECTED_BLOCKED_STATE_ID,
    PAYLOAD_STOPPED_BLOCKED_STATE_ID,
    REASON_RESOLUTION_REJECTED,
    REASON_STOPPED,
    ResolutionRejection,
    Situation,
)
from amoeba.store import (
    BlockedKind,
    BlockedState,
    BlockEffect,
    CommandKind,
    JournalEntry,
    NodeStatus,
    Resolution,
    ResolutionOutcome,
    StatusEffect,
)

PAUSED_AT = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
PAUSED = Situation.PAUSED_RUN


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


def _checkpoint(
    kind: str | None = "loop_exhausted",
    *,
    is_loop: object = True,
    paused_at: datetime | None = PAUSED_AT,
) -> RunCheckpoint:
    return RunCheckpoint.model_validate(
        {"kind": kind, "is_loop": is_loop, "paused_at": paused_at}
    )


def _rejection(answer: Acknowledgment) -> str:
    assert answer.outcome is ResolutionOutcome.REJECTED
    assert answer.code is not None
    assert isinstance(answer.effect, BlockEffect)
    return answer.code


@pytest.mark.parametrize(
    ("decision", "instructions", "situation", "checkpoint", "code"),
    [
        ("retry", None, Situation.UNRESOLVABLE, _checkpoint(), "unresolvable"),
        (None, None, Situation.UNRESOLVABLE, None, "unresolvable"),
        ("maybe", None, PAUSED, _checkpoint(), "unknown_decision"),
        (None, None, PAUSED, _checkpoint(), "decision_required"),
        (None, None, Situation.BEFORE_RUN, None, "decision_required"),
        ("rerun", None, Situation.NO_DECISION, None, "decision_not_applicable"),
        ("retry", None, Situation.ENDED_RUN, None, "decision_not_applicable"),
        ("handled", None, Situation.COMPLETED_OUTCOME, None, "decision_not_applicable"),
        ("rerun", None, PAUSED, _checkpoint(), "decision_not_applicable"),
        ("accept", None, PAUSED, _checkpoint(is_loop=False), "not_at_loop"),
        ("accept", None, PAUSED, _checkpoint(is_loop=None), "not_at_loop"),
        ("accept", None, PAUSED, _checkpoint(is_loop="yes"), "not_at_loop"),
        ("accept", None, PAUSED, None, "not_at_loop"),
        (
            "accept",
            None,
            PAUSED,
            _checkpoint("usage_limit"),
            "usage_limit_pause",
        ),
        ("retry", None, PAUSED, _checkpoint(None), "checkpoint_unknown"),
        ("retry", None, PAUSED, _checkpoint(paused_at=None), "checkpoint_unknown"),
        ("retry", None, PAUSED, None, "checkpoint_unknown"),
        ("accept", None, PAUSED, _checkpoint(None), "checkpoint_unknown"),
        ("accept", None, PAUSED, _checkpoint(paused_at=None), "checkpoint_unknown"),
        (
            "retry",
            None,
            PAUSED,
            _checkpoint("interactive_checkpoint"),
            "interactive_checkpoint",
        ),
        ("handled", "do it", PAUSED, _checkpoint(), "instructions_not_applicable"),
        ("rerun", "do it", Situation.ENDED_RUN, None, "instructions_not_applicable"),
        ("stop", "do it", PAUSED, _checkpoint(), "instructions_not_applicable"),
    ],
)
def test_each_check_rejects_with_its_code(
    decision: str | None,
    instructions: str | None,
    situation: Situation,
    checkpoint: RunCheckpoint | None,
    code: str,
) -> None:
    answer = judge_resolution(_blocked(decision, instructions), situation, checkpoint)

    assert _rejection(answer) == code


def test_accept_refused_when_not_at_loop() -> None:
    for is_loop in (False, None):
        answer = judge_resolution(
            _blocked("accept"), PAUSED, _checkpoint(is_loop=is_loop)
        )
        assert _rejection(answer) == ResolutionRejection.NOT_AT_LOOP


def test_usage_limit_refuses_accept_at_a_loop_but_not_retry() -> None:
    checkpoint = _checkpoint("usage_limit", is_loop=True)

    assert (
        _rejection(judge_resolution(_blocked("accept"), PAUSED, checkpoint))
        == "usage_limit_pause"
    )
    assert judge_resolution(_blocked("retry"), PAUSED, checkpoint).code is None


def test_the_first_failing_check_wins() -> None:
    """Not at a loop, and instructions on a decision that takes none."""
    answer = judge_resolution(
        _blocked("handled", "x"), PAUSED, _checkpoint(is_loop=False)
    )

    assert _rejection(answer) == "instructions_not_applicable"
    unresolvable = judge_resolution(_blocked("maybe"), Situation.UNRESOLVABLE, None)
    assert _rejection(unresolvable) == "unresolvable"


def test_a_rejection_blocks_again_and_lists_what_is_allowed() -> None:
    answer = judge_resolution(_blocked("accept"), PAUSED, _checkpoint(is_loop=False))

    assert answer.reason is not None
    effect = answer.effect
    assert isinstance(effect, BlockEffect)
    assert effect.context == "resolution rejected: not_at_loop"
    assert effect.payload == {
        "reason": REASON_RESOLUTION_REJECTED,
        PAYLOAD_CODE: "not_at_loop",
        PAYLOAD_DETAIL: answer.reason,
        PAYLOAD_REJECTED_BLOCKED_STATE_ID: "b-1",
        PAYLOAD_ALLOWED: sorted(d.value for d in ALLOWED[PAUSED]),
    }


@pytest.mark.parametrize(
    ("decision", "instructions", "situation", "checkpoint"),
    [
        ("retry", None, PAUSED, _checkpoint()),
        ("retry", "narrow it", PAUSED, _checkpoint("awaits_human")),
        ("accept", "ok", PAUSED, _checkpoint(is_loop=True)),
        ("handled", None, PAUSED, None),
        ("rerun", None, Situation.COMPLETED_OUTCOME, None),
        ("rerun", None, Situation.ENDED_RUN, None),
        ("rerun", None, Situation.BEFORE_RUN, None),
        (None, None, Situation.NO_DECISION, None),
    ],
)
def test_these_are_applied_with_no_effect(
    decision: str | None,
    instructions: str | None,
    situation: Situation,
    checkpoint: RunCheckpoint | None,
) -> None:
    answer = judge_resolution(_blocked(decision, instructions), situation, checkpoint)

    assert answer == Acknowledgment(ResolutionOutcome.APPLIED, None, None, None)


def test_accept_of_a_completed_outcome_marks_the_step_done() -> None:
    answer = judge_resolution(_blocked("accept"), Situation.COMPLETED_OUTCOME, None)

    assert answer.outcome is ResolutionOutcome.APPLIED
    assert answer.effect == StatusEffect(NodeStatus.DONE)


@pytest.mark.parametrize("situation", [PAUSED, Situation.COMPLETED_OUTCOME])
def test_stop_parks_the_node_as_a_block(situation: Situation) -> None:
    answer = judge_resolution(_blocked("stop"), situation, _checkpoint())

    assert answer.outcome is ResolutionOutcome.APPLIED
    assert answer.effect == BlockEffect(
        context="stopped by pm",
        payload={"reason": REASON_STOPPED, PAYLOAD_STOPPED_BLOCKED_STATE_ID: "b-1"},
    )


def test_a_decision_on_a_human_step_is_not_applicable() -> None:
    answer = judge_resolution(_blocked("rerun"), Situation.NO_DECISION, None)

    assert _rejection(answer) == "decision_not_applicable"


def test_a_bare_resolution_of_a_human_step_is_applied() -> None:
    answer = judge_resolution(_blocked(), Situation.NO_DECISION, None)

    assert answer.outcome is ResolutionOutcome.APPLIED and answer.effect is None


def test_an_unresolved_state_is_a_programming_error() -> None:
    unresolved = BlockedState(id="b", node_id="n", kind=BlockedKind.HUMAN, context="c")

    with pytest.raises(ValueError, match="not resolved"):
        judge_resolution(unresolved, PAUSED, None)


# -- checkpoint_of -----------------------------------------------------------


def _run_entry(document: object) -> JournalEntry:
    return JournalEntry(
        id="e",
        project_id="p",
        node_id="n",
        kind=CommandKind.SQ_RUN,
        result={RESULT_OUTCOME_DOCUMENT: document},
    )


def test_checkpoint_of_reads_the_recorded_document() -> None:
    document = {
        "run_id": "r",
        "outcome": "paused",
        "checkpoint": {"kind": "loop_exhausted", "is_loop": True},
    }

    checkpoint = checkpoint_of(_run_entry(document))

    assert checkpoint is not None and checkpoint.kind == "loop_exhausted"


@pytest.mark.parametrize(
    "document",
    [None, "text", {"outcome": "paused"}, {"run_id": "r", "outcome": "nonsense"}],
)
def test_checkpoint_of_never_raises_on_a_bad_document(document: object) -> None:
    assert checkpoint_of(_run_entry(document)) is None


def test_checkpoint_of_no_entry_or_no_result_is_none() -> None:
    assert checkpoint_of(None) is None
    bare = JournalEntry(id="e", project_id="p", node_id="n", kind=CommandKind.SQ_RUN)
    assert checkpoint_of(bare) is None
