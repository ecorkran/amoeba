"""D4: the supervised outcome plan, one case per row of the outcome map."""

from __future__ import annotations

from typing import cast

import pytest

from amoeba.process import RunOutcomeDocument
from amoeba.runner.ingest.outcome import (
    PAYLOAD_CHECKPOINT,
    PAYLOAD_COUNT,
    PAYLOAD_FAILURE,
    PAYLOAD_QUESTION,
    PAYLOAD_REASON,
    PAYLOAD_RUN_ID,
    PAYLOAD_STEP,
    OutcomePlan,
    plan_supervised,
)
from amoeba.runner.launch import STDERR_TAIL_LIMIT_BYTES
from amoeba.runner.observed import RunEnded, RunVanished
from amoeba.runner.supervise import (
    REASON_AGENT_QUESTION,
    REASON_AUTO_RESUME_EXHAUSTED,
    REASON_FAILED,
    REASON_PAUSED,
)
from amoeba.store import BlockedKind, JournalOutcome

RUN_ID = "run-20261029-p456-aaaa1111"
LIMIT = 3
RESETS_AT = "2026-10-29T18:00:00+00:00"


def _ended(outcome: str, **fields: object) -> RunEnded:
    document = {"run_id": RUN_ID, "outcome": outcome, **fields}
    return RunEnded(RunOutcomeDocument.model_validate(document))


def _plan(finished: RunEnded | RunVanished, count: int = 0) -> OutcomePlan:
    return plan_supervised(finished, RUN_ID, count, LIMIT)


def _payload(plan: OutcomePlan) -> dict[str, object]:
    assert plan.block is not None and plan.block.payload is not None
    return dict(plan.block.payload)


def test_completed_resolves_and_completes_the_node() -> None:
    assert _plan(_ended("completed")) == OutcomePlan(
        None, JournalOutcome.COMPLETED, complete_node=True
    )


def test_an_agent_question_blocks_on_a_human_with_its_question() -> None:
    checkpoint = {"kind": "agent_question", "step": "design-0", "question": "Which?"}

    plan = _plan(_ended("paused", checkpoint=checkpoint))

    assert plan.entry_outcome is JournalOutcome.COMPLETED
    assert not plan.complete_node
    assert plan.block is not None and plan.block.kind is BlockedKind.HUMAN
    assert _payload(plan) == {
        PAYLOAD_RUN_ID: RUN_ID,
        PAYLOAD_REASON: REASON_AGENT_QUESTION,
        PAYLOAD_STEP: "design-0",
        PAYLOAD_QUESTION: "Which?",
    }


def test_an_agent_question_without_a_question_carries_null() -> None:
    plan = _plan(
        _ended("paused", checkpoint={"kind": "agent_question", "step": "design-0"})
    )

    assert _payload(plan)[PAYLOAD_QUESTION] is None


def test_a_question_longer_than_the_bound_is_cut() -> None:
    question = "q" * (STDERR_TAIL_LIMIT_BYTES * 3)
    checkpoint = {"kind": "agent_question", "step": "s", "question": question}

    payload = _payload(_plan(_ended("paused", checkpoint=checkpoint)))

    assert len(cast("str", payload[PAYLOAD_QUESTION]).encode()) == (
        STDERR_TAIL_LIMIT_BYTES
    )


@pytest.mark.parametrize(
    "checkpoint",
    [
        {"kind": "awaits_human", "step": "branch-10"},
        {"kind": "loop_exhausted", "step": "tasks-0"},
        {"kind": "usage_limit", "step": "design-0"},
        {"kind": "a_kind_from_the_future", "step": "design-0"},
    ],
)
def test_any_other_pause_blocks_on_the_checkpoint_with_it_in_the_payload(
    checkpoint: dict[str, str],
) -> None:
    plan = _plan(_ended("paused", checkpoint=checkpoint))

    assert plan.entry_outcome is JournalOutcome.COMPLETED
    assert plan.block is not None and plan.block.kind is BlockedKind.SQ_CHECKPOINT
    payload = _payload(plan)
    assert payload[PAYLOAD_REASON] == REASON_PAUSED
    reported = cast("dict[str, object]", payload[PAYLOAD_CHECKPOINT])
    assert (reported["kind"], reported["step"]) == (
        checkpoint["kind"],
        checkpoint["step"],
    )


@pytest.mark.parametrize("kind", ["artifact_missing", "cost_cap", "meltdown"])
def test_any_other_failure_blocks_a_human_with_the_failure(kind: str) -> None:
    failure = {"kind": kind, "step": "design-0", "message": "m"}

    plan = _plan(_ended("failed", failure=failure))

    assert plan.entry_outcome is JournalOutcome.COMPLETED
    assert plan.block is not None and plan.block.kind is BlockedKind.HUMAN
    assert _payload(plan) == {
        PAYLOAD_RUN_ID: RUN_ID,
        PAYLOAD_REASON: REASON_FAILED,
        PAYLOAD_FAILURE: failure,
    }


def test_a_failure_carries_the_agent_text_when_squadron_sent_it() -> None:
    failure = {
        "kind": "artifact_missing",
        "step": "s",
        "message": "m",
        "agent_text": "?",
    }

    payload = _payload(_plan(_ended("failed", failure=failure)))

    assert cast("dict[str, object]", payload[PAYLOAD_FAILURE])["agent_text"] == "?"


def test_a_vanished_run_blocks_a_human_and_resolves_failed() -> None:
    plan = _plan(RunVanished())

    assert plan.entry_outcome is JournalOutcome.FAILED
    assert plan.block is not None and plan.block.kind is BlockedKind.HUMAN


@pytest.mark.parametrize(
    "finished",
    [
        _ended("orphaned"),
        _ended("failed", failure={"kind": "stall", "step": "design-0"}),
        _ended(
            "paused",
            checkpoint={
                "kind": "usage_limit",
                "step": "design-0",
                "resets_at": RESETS_AT,
            },
        ),
    ],
)
@pytest.mark.parametrize("count", [0, LIMIT - 1])
def test_a_transient_outcome_under_the_bound_resolves_without_a_block(
    finished: RunEnded, count: int
) -> None:
    plan = _plan(finished, count)

    assert plan.block is None
    assert not plan.complete_node


def test_a_transient_orphan_resolves_failed_and_the_others_completed() -> None:
    assert _plan(_ended("orphaned")).entry_outcome is JournalOutcome.FAILED
    stalled = _ended("failed", failure={"kind": "stall", "step": "s"})
    assert _plan(stalled).entry_outcome is JournalOutcome.COMPLETED


def test_a_transient_failure_at_the_bound_blocks_with_the_count_and_failure() -> None:
    failure = {"kind": "stall", "step": "design-0", "message": "m"}

    plan = _plan(_ended("failed", failure=failure), LIMIT)

    assert plan.block is not None and plan.block.kind is BlockedKind.HUMAN
    assert _payload(plan) == {
        PAYLOAD_RUN_ID: RUN_ID,
        PAYLOAD_REASON: REASON_AUTO_RESUME_EXHAUSTED,
        PAYLOAD_STEP: "design-0",
        PAYLOAD_COUNT: LIMIT,
        PAYLOAD_FAILURE: failure,
    }


def test_a_transient_pause_at_the_bound_blocks_with_the_checkpoint() -> None:
    checkpoint = {"kind": "usage_limit", "step": "tasks-0", "resets_at": RESETS_AT}

    payload = _payload(_plan(_ended("paused", checkpoint=checkpoint), LIMIT))

    assert payload[PAYLOAD_REASON] == REASON_AUTO_RESUME_EXHAUSTED
    assert payload[PAYLOAD_STEP] == "tasks-0"
    reported = cast("dict[str, object]", payload[PAYLOAD_CHECKPOINT])
    assert reported["kind"] == "usage_limit"


def test_an_orphan_at_the_bound_has_a_null_step_and_no_evidence() -> None:
    payload = _payload(_plan(_ended("orphaned"), LIMIT))

    assert payload[PAYLOAD_STEP] is None
    assert PAYLOAD_FAILURE not in payload and PAYLOAD_CHECKPOINT not in payload


@pytest.mark.parametrize(
    "outcome", ["timed_out", "not_found", "unreadable", "unknown_status"]
)
def test_an_outcome_that_is_not_an_end_state_is_refused(outcome: str) -> None:
    with pytest.raises(ValueError, match="not an end state"):
        _plan(_ended(outcome))
