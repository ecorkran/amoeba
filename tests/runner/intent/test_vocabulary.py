"""The intent body model and the ``until`` applicability rule (D1, D3, D4)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from amoeba.runner.intent.vocabulary import (
    IntentBody,
    IntentKind,
    TargetKind,
    until_applies,
)
from amoeba.runner.lifecycle.steps import LifecycleStep

_SLICE_STEPS = {
    LifecycleStep.SLICE_DESIGN,
    LifecycleStep.TASKS,
    LifecycleStep.IMPLEMENTATION,
    LifecycleStep.MERGE,
}


@pytest.mark.parametrize(
    ("payload", "kind", "until"),
    [
        ({"intent": "drive"}, IntentKind.DRIVE, None),
        ({"intent": "drive", "until": "tasks"}, IntentKind.DRIVE, LifecycleStep.TASKS),
        ({"intent": "exclude"}, IntentKind.EXCLUDE, None),
        ({"intent": "pause"}, IntentKind.PAUSE, None),
        ({"intent": "resume"}, IntentKind.RESUME, None),
        ({"intent": "clear"}, IntentKind.CLEAR, None),
    ],
)
def test_each_body_form_parses(
    payload: dict[str, Any], kind: IntentKind, until: LifecycleStep | None
) -> None:
    body = IntentBody.model_validate(payload)
    assert (body.intent, body.until) == (kind, until)


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "drive", "untill": "tasks"},
        {"intent": "launch"},
        {"intent": "drive", "until": "deploy"},
        {"intent": "exclude", "until": "tasks"},
        {"intent": "pause", "until": "tasks"},
        {"intent": "resume", "until": "tasks"},
        {"intent": "clear", "until": "tasks"},
        {},
        ["drive"],
        "drive",
    ],
)
def test_malformed_bodies_fail(payload: object) -> None:
    with pytest.raises(ValidationError):
        IntentBody.model_validate(payload)


@pytest.mark.parametrize("target", list(TargetKind))
@pytest.mark.parametrize("step", list(LifecycleStep))
def test_until_applies_by_target_kind(target: TargetKind, step: LifecycleStep) -> None:
    expected = step in _SLICE_STEPS if target is TargetKind.SLICE else True
    assert until_applies(target, step) is expected
