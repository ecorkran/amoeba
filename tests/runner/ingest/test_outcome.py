"""D6: every row of the outcome-to-block table, with no store and no I/O."""

from __future__ import annotations

from typing import cast

import pytest

from amoeba.process import FailureKind, RunOutcome, RunOutcomeDocument
from amoeba.runner.ingest.outcome import (
    PAYLOAD_FAILURE,
    PAYLOAD_REASON,
    PAYLOAD_RUN_ID,
    REASON_FAILED,
    REASON_ORPHANED,
    REASON_VANISHED,
    UNKNOWN_TEXT,
    OutcomePlan,
    cut_to_bound,
    plan_outcome,
)
from amoeba.runner.launch import STDERR_TAIL_LIMIT_BYTES
from amoeba.runner.observed import RunEnded, RunVanished
from amoeba.store import BlockedKind, JournalOutcome

RUN_ID = "amoeba-20261024T101500Z-0123456789ab"


def _ended(outcome: RunOutcome, **fields: object) -> RunEnded:
    document = RunOutcomeDocument.model_validate(
        {"run_id": RUN_ID, "outcome": outcome.value, **fields}
    )
    return RunEnded(document)


def _plan(finished: RunEnded | RunVanished) -> OutcomePlan:
    return plan_outcome(finished, RUN_ID)


def test_completed_has_no_block_and_resolves_completed() -> None:
    assert _plan(_ended(RunOutcome.COMPLETED)) == OutcomePlan(
        None, JournalOutcome.COMPLETED
    )


def test_paused_blocks_on_the_checkpoint_with_no_payload() -> None:
    plan = _plan(
        _ended(
            RunOutcome.PAUSED, checkpoint={"kind": "awaits_human", "step": "branch-10"}
        )
    )

    assert plan.entry_outcome is JournalOutcome.COMPLETED
    assert plan.block is not None
    assert plan.block.kind is BlockedKind.SQ_CHECKPOINT
    assert plan.block.context == f"paused: awaits_human at branch-10, run {RUN_ID}"
    assert plan.block.payload is None


@pytest.mark.parametrize(
    "checkpoint",
    [None, {}, {"kind": None, "step": None}],
)
def test_a_paused_run_without_kind_or_step_says_unknown(
    checkpoint: dict[str, object] | None,
) -> None:
    plan = _plan(_ended(RunOutcome.PAUSED, checkpoint=checkpoint))

    assert plan.block is not None
    assert plan.block.context == (
        f"paused: {UNKNOWN_TEXT} at {UNKNOWN_TEXT}, run {RUN_ID}"
    )


@pytest.mark.parametrize("kind", [member.value for member in FailureKind])
def test_failed_blocks_on_a_human_with_the_failure_as_reported(kind: str) -> None:
    failure = {"kind": kind, "step": "implement-6", "message": "it broke"}

    plan = _plan(_ended(RunOutcome.FAILED, failure=failure))

    assert plan.entry_outcome is JournalOutcome.COMPLETED
    assert plan.block is not None
    assert plan.block.kind is BlockedKind.HUMAN
    assert plan.block.payload == {
        PAYLOAD_RUN_ID: RUN_ID,
        PAYLOAD_REASON: REASON_FAILED,
        PAYLOAD_FAILURE: failure,
    }
    assert kind in plan.block.context


def test_failed_with_an_unrecognized_kind_is_blocked_all_the_same() -> None:
    failure = {"kind": "meltdown", "step": "s", "message": "m"}

    plan = _plan(_ended(RunOutcome.FAILED, failure=failure))

    assert plan.block is not None
    assert plan.block.payload is not None
    assert plan.block.payload[PAYLOAD_FAILURE] == failure
    assert "meltdown" in plan.block.context


def test_failed_with_no_failure_object_blocks_with_a_null_failure() -> None:
    plan = _plan(_ended(RunOutcome.FAILED))

    assert plan.entry_outcome is JournalOutcome.COMPLETED
    assert plan.block is not None
    assert plan.block.payload == {
        PAYLOAD_RUN_ID: RUN_ID,
        PAYLOAD_REASON: REASON_FAILED,
        PAYLOAD_FAILURE: None,
    }
    assert UNKNOWN_TEXT in plan.block.context


@pytest.mark.parametrize(
    ("finished", "reason"),
    [
        (_ended(RunOutcome.ORPHANED), REASON_ORPHANED),
        (RunVanished(), REASON_VANISHED),
    ],
)
def test_orphaned_and_vanished_block_on_a_human_and_resolve_failed(
    finished: RunEnded | RunVanished, reason: str
) -> None:
    plan = _plan(finished)

    assert plan.entry_outcome is JournalOutcome.FAILED
    assert plan.block is not None
    assert plan.block.kind is BlockedKind.HUMAN
    assert plan.block.payload == {PAYLOAD_RUN_ID: RUN_ID, PAYLOAD_REASON: reason}
    assert RUN_ID in plan.block.context


@pytest.mark.parametrize(
    "outcome",
    [
        RunOutcome.TIMED_OUT,
        RunOutcome.NOT_FOUND,
        RunOutcome.UNREADABLE,
        RunOutcome.UNKNOWN_STATUS,
    ],
)
def test_an_outcome_that_is_not_an_end_state_is_refused(outcome: RunOutcome) -> None:
    with pytest.raises(ValueError, match="not an end state"):
        _plan(_ended(outcome))


def test_an_oversized_failure_message_is_cut_to_the_bound() -> None:
    message = "x" * (STDERR_TAIL_LIMIT_BYTES * 3)

    plan = _plan(
        _ended(
            RunOutcome.FAILED,
            failure={"kind": "stall", "step": "s", "message": message},
        )
    )

    assert plan.block is not None and plan.block.payload is not None
    failure = cast("dict[str, str]", plan.block.payload[PAYLOAD_FAILURE])
    assert len(failure["message"].encode()) == STDERR_TAIL_LIMIT_BYTES


def test_oversized_checkpoint_text_is_cut_in_the_context() -> None:
    long = "k" * (STDERR_TAIL_LIMIT_BYTES * 2)

    plan = _plan(_ended(RunOutcome.PAUSED, checkpoint={"kind": long, "step": long}))

    assert plan.block is not None
    assert len(plan.block.context.encode()) < 2 * STDERR_TAIL_LIMIT_BYTES + 200


def test_the_cut_never_splits_a_character() -> None:
    text = "é" * STDERR_TAIL_LIMIT_BYTES  # two bytes each

    cut = cut_to_bound(text)

    assert len(cut.encode()) <= STDERR_TAIL_LIMIT_BYTES
    assert set(cut) == {"é"}
    assert cut_to_bound("short") == "short"
