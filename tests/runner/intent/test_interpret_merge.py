"""``interpret``: merging an intent into the target's row (D1's table, D5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from amoeba.runner.intent.apply import interpret
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import (
    AcknowledgmentOutcome,
    Channel,
    ClearDesiredState,
    DesiredState,
    Message,
    SetDesiredState,
)

APPLIED = AcknowledgmentOutcome.APPLIED
NO_OP = AcknowledgmentOutcome.NO_OP
NODE = None  # the project target; the merge rules do not depend on the target

NONE_ROW = None
DRIVE_ONLY = {"drive": True}
DRIVE_UNTIL = {"drive": True, "drive_until_step": "tasks"}
HOLD_ONLY = {"hold": True}
DRIVE_HOLD = {"drive": True, "hold": True}
EXCLUDED = {"drive": False}


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


def _interpret(body: dict[str, Any], row: dict[str, Any] | None):
    message = Message(
        seq=1, id="m-1", project_id="demo", channel=Channel.INTENT, payload=body
    )
    return interpret(message, LifecycleTree([]), _row(row))


def _set(**fields: Any) -> SetDesiredState:
    return SetDesiredState(node_id=NODE, **fields)


CLEAR = ClearDesiredState(node_id=NODE)

#: (id, current row, body, outcome, expected change)
CASES = [
    # drive
    ("drive/none", NONE_ROW, {"intent": "drive"}, APPLIED, _set(drive=True)),
    ("drive/drive", DRIVE_ONLY, {"intent": "drive"}, NO_OP, None),
    (
        "drive/until-clears",
        DRIVE_UNTIL,
        {"intent": "drive"},
        APPLIED,
        _set(drive=True),
    ),
    (
        "drive/hold-kept",
        HOLD_ONLY,
        {"intent": "drive"},
        APPLIED,
        _set(drive=True, hold=True),
    ),
    (
        "drive/excluded",
        EXCLUDED,
        {"intent": "drive"},
        APPLIED,
        _set(drive=True),
    ),
    (
        "drive-until/none",
        NONE_ROW,
        {"intent": "drive", "until": "tasks"},
        APPLIED,
        _set(drive=True, drive_until_step="tasks"),
    ),
    (
        "drive-until/same",
        DRIVE_UNTIL,
        {"intent": "drive", "until": "tasks"},
        NO_OP,
        None,
    ),
    (
        "drive-until/replaces",
        DRIVE_UNTIL,
        {"intent": "drive", "until": "implementation"},
        APPLIED,
        _set(drive=True, drive_until_step="implementation"),
    ),
    (
        "drive-until/restricts-open-drive",
        DRIVE_ONLY,
        {"intent": "drive", "until": "slice_design"},
        APPLIED,
        _set(drive=True, drive_until_step="slice_design"),
    ),
    (
        "drive-until/hold-kept",
        DRIVE_HOLD,
        {"intent": "drive", "until": "tasks"},
        APPLIED,
        _set(drive=True, drive_until_step="tasks", hold=True),
    ),
    # exclude
    ("exclude/none", NONE_ROW, {"intent": "exclude"}, APPLIED, _set(drive=False)),
    ("exclude/excluded", EXCLUDED, {"intent": "exclude"}, NO_OP, None),
    (
        "exclude/clears-until",
        DRIVE_UNTIL,
        {"intent": "exclude"},
        APPLIED,
        _set(drive=False),
    ),
    (
        "exclude/hold-kept",
        DRIVE_HOLD,
        {"intent": "exclude"},
        APPLIED,
        _set(drive=False, hold=True),
    ),
    # pause
    ("pause/none", NONE_ROW, {"intent": "pause"}, APPLIED, _set(hold=True)),
    ("pause/hold", HOLD_ONLY, {"intent": "pause"}, NO_OP, None),
    (
        "pause/drive-kept",
        DRIVE_ONLY,
        {"intent": "pause"},
        APPLIED,
        _set(drive=True, hold=True),
    ),
    (
        "pause/until-kept",
        DRIVE_UNTIL,
        {"intent": "pause"},
        APPLIED,
        _set(drive=True, drive_until_step="tasks", hold=True),
    ),
    # resume
    ("resume/none", NONE_ROW, {"intent": "resume"}, NO_OP, None),
    ("resume/no-hold", DRIVE_ONLY, {"intent": "resume"}, NO_OP, None),
    ("resume/only-setting", HOLD_ONLY, {"intent": "resume"}, APPLIED, CLEAR),
    ("resume/drive-kept", DRIVE_HOLD, {"intent": "resume"}, APPLIED, _set(drive=True)),
    # clear
    ("clear/none", NONE_ROW, {"intent": "clear"}, NO_OP, None),
    ("clear/drive", DRIVE_ONLY, {"intent": "clear"}, APPLIED, CLEAR),
    ("clear/hold", HOLD_ONLY, {"intent": "clear"}, APPLIED, CLEAR),
    ("clear/everything", DRIVE_HOLD, {"intent": "clear"}, APPLIED, CLEAR),
]


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
    assert result.desired_state == _set(drive=True, hold=True)


def test_a_hold_is_never_stored_false() -> None:
    result = _interpret({"intent": "resume"}, DRIVE_HOLD)
    assert isinstance(result.desired_state, SetDesiredState)
    assert result.desired_state.hold is None
