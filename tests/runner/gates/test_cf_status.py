"""D1: every captured `cf status --json` state maps to its position."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amoeba.runner.gates.cf_status import (
    ENTRY_GATE,
    EXIT_GATE,
    CFActiveSlice,
    GatePosition,
    parse_status,
    position_of,
)
from amoeba.runner.lifecycle.steps import LifecycleStep

STATUS_FIXTURES = Path(__file__).parents[2] / "fixtures" / "cf" / "status"


def _active(name: str) -> CFActiveSlice:
    document = json.loads((STATUS_FIXTURES / f"{name}.json").read_text())
    parsed = parse_status(document)
    assert parsed is not None, f"{name} did not parse"
    return parsed


@pytest.mark.parametrize(
    ("fixture", "position"),
    [
        ("needs_design", GatePosition.NEEDS_DESIGN),
        ("pending_review_slice", GatePosition.AT_SLICE_GATE),
        ("review_failed_slice", GatePosition.AT_SLICE_GATE),
        ("needs_tasks", GatePosition.PAST_SLICE_GATE),
        ("gate_exempt_review_none", GatePosition.PAST_SLICE_GATE),
        ("pending_review_tasks", GatePosition.AT_TASKS_GATE),
        ("review_failed_tasks", GatePosition.AT_TASKS_GATE),
        ("in_implementation_no_task_done", GatePosition.PAST_TASKS_GATE),
        ("in_implementation", GatePosition.PAST_TASKS_GATE),
        ("pending_review_code", GatePosition.AT_CODE_GATE),
        ("review_failed_code", GatePosition.AT_CODE_GATE),
        ("complete", GatePosition.PAST_CODE_GATE),
        ("worktree", GatePosition.PAST_CODE_GATE),
        ("pending_decision", GatePosition.PENDING_DECISION),
        ("no_active_slice", GatePosition.UNKNOWN),
    ],
)
def test_each_captured_state_maps_to_its_position(
    fixture: str, position: GatePosition
) -> None:
    assert position_of(_active(fixture)) is position


def test_the_scale_is_ordered_and_the_off_scale_positions_are_marked() -> None:
    scale = [
        GatePosition.NEEDS_DESIGN,
        GatePosition.AT_SLICE_GATE,
        GatePosition.PAST_SLICE_GATE,
        GatePosition.AT_TASKS_GATE,
        GatePosition.PAST_TASKS_GATE,
        GatePosition.AT_CODE_GATE,
        GatePosition.PAST_CODE_GATE,
    ]
    assert scale == sorted(scale)
    assert all(position.on_scale for position in scale)
    assert not GatePosition.PENDING_DECISION.on_scale
    assert not GatePosition.UNKNOWN.on_scale


def _document(**active: object) -> dict[str, object]:
    return {"activeSlice": {"name": "alpha", "index": 900, **active}}


def test_status_text_is_trimmed_and_lower_cased() -> None:
    parsed = parse_status(_document(status="  Needs-Tasks "))

    assert parsed is not None
    assert position_of(parsed) is GatePosition.PAST_SLICE_GATE


def test_review_type_text_is_trimmed_and_lower_cased() -> None:
    parsed = parse_status(
        _document(
            status="Pending-Review",
            gateInfo={"reviewType": " TASKS ", "rationale": "r"},
        )
    )

    assert parsed is not None
    assert position_of(parsed) is GatePosition.AT_TASKS_GATE


@pytest.mark.parametrize(
    "active",
    [
        {"status": "brand-new-status"},
        {
            "status": "pending-review",
            "gateInfo": {"reviewType": "arch", "rationale": "r"},
        },
        {"status": "review-failed"},
        {"status": "pending-review", "gateInfo": {"reviewType": "", "rationale": "r"}},
        {"status": "no-active-slice"},
    ],
    ids=[
        "unknown status",
        "unknown review type",
        "review gate without gateInfo",
        "empty review type",
        "no active slice",
    ],
)
def test_anything_the_table_does_not_name_is_unknown(active: dict[str, object]) -> None:
    parsed = parse_status(_document(**active))

    assert parsed is not None
    assert position_of(parsed) is GatePosition.UNKNOWN


def test_rationale_and_pending_decisions_are_carried_and_never_matched() -> None:
    failed = _active("review_failed_slice")
    decision = _active("pending_decision")

    assert failed.gate_info is not None
    assert "FAIL" in failed.gate_info.rationale
    assert decision.pending_decisions is not None
    assert decision.pending_decisions[0].heading == "Decision"
    assert position_of(failed) is GatePosition.AT_SLICE_GATE


def test_a_gate_exempt_state_is_carried() -> None:
    assert _active("gate_exempt_review_none").gate_exempt == "review-none"
    assert _active("needs_tasks").gate_exempt is None


def test_keys_cf_adds_are_ignored() -> None:
    parsed = parse_status(_document(status="complete", futureKey={"a": 1}))

    assert parsed is not None and position_of(parsed) is GatePosition.PAST_CODE_GATE


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"activeSlice": "complete"},
        {"activeSlice": {"name": "alpha", "index": "900", "status": "complete"}},
        {"activeSlice": {"name": "alpha", "index": 900}},
        {"activeSlice": {"name": "alpha", "index": 900, "status": 7}},
    ],
    ids=[
        "no activeSlice",
        "not an object",
        "index as text",
        "no status",
        "status number",
    ],
)
def test_a_document_with_the_wrong_shape_is_none(document: dict[str, object]) -> None:
    assert parse_status(document) is None


def test_the_exit_and_entry_gates_of_each_step() -> None:
    assert EXIT_GATE == {
        LifecycleStep.SLICE_DESIGN: GatePosition.AT_SLICE_GATE,
        LifecycleStep.TASKS: GatePosition.AT_TASKS_GATE,
        LifecycleStep.IMPLEMENTATION: GatePosition.AT_CODE_GATE,
    }
    assert ENTRY_GATE == {
        LifecycleStep.TASKS: GatePosition.AT_SLICE_GATE,
        LifecycleStep.IMPLEMENTATION: GatePosition.AT_TASKS_GATE,
    }
    assert LifecycleStep.SLICE_DESIGN not in ENTRY_GATE
