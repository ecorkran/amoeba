"""``interpret``: merging an intent into the target's row (D1's table, D5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from amoeba.runner.intent.apply import Interpretation, interpret
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import (
    AcknowledgmentOutcome,
    Channel,
    ClearDesiredState,
    DesiredState,
    Message,
    SetDesiredState,
)

from .merge_cases import (
    CASES,
    DRIVE_HOLD,
    HOLD_ONLY,
    NO_OP,
    set_row,
)


def _row(fields: dict[str, Any] | None) -> DesiredState | None:
    if fields is None:
        return None
    return DesiredState(
        id="d-1",
        project_id="demo",
        message_id="m-0",
        updated_at=datetime(2026, 10, 23, tzinfo=UTC),
        **fields,
    )


def _interpret(body: dict[str, Any], row: dict[str, Any] | None) -> Interpretation:
    message = Message(
        seq=1, id="m-1", project_id="demo", channel=Channel.INTENT, payload=body
    )
    return interpret(message, LifecycleTree([]), _row(row))


@pytest.mark.parametrize(
    ("row", "body", "outcome", "change"),
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_intent_merges_into_the_row(
    row: dict[str, Any] | None,
    body: dict[str, Any],
    outcome: AcknowledgmentOutcome,
    change: SetDesiredState | ClearDesiredState | None,
) -> None:
    result = _interpret(body, row)
    assert result.outcome is outcome
    assert result.desired_state == change
    assert result.reason is None


def test_same_intent_twice_is_no_op() -> None:
    first = _interpret({"intent": "pause"}, None)
    assert isinstance(first.desired_state, SetDesiredState)
    stored = {
        "drive": first.desired_state.drive,
        "hold": first.desired_state.hold,
    }
    assert _interpret({"intent": "pause"}, stored).outcome is NO_OP


def test_pause_then_drive_keeps_the_pause() -> None:
    result = _interpret({"intent": "drive"}, HOLD_ONLY)
    assert result.desired_state == set_row(drive=True, hold=True)


def test_a_hold_is_never_stored_false() -> None:
    result = _interpret({"intent": "resume"}, DRIVE_HOLD)
    assert isinstance(result.desired_state, SetDesiredState)
    assert result.desired_state.hold is None
