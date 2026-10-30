"""The intent body model (D1, D3, D4; slice 132, D7: no ``until``)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from amoeba.runner.intent.vocabulary import IntentBody, IntentKind, IntentRejection


@pytest.mark.parametrize(
    ("payload", "kind"),
    [
        ({"intent": "drive"}, IntentKind.DRIVE),
        ({"intent": "exclude"}, IntentKind.EXCLUDE),
        ({"intent": "pause"}, IntentKind.PAUSE),
        ({"intent": "resume"}, IntentKind.RESUME),
        ({"intent": "clear"}, IntentKind.CLEAR),
    ],
)
def test_each_body_form_parses(payload: dict[str, Any], kind: IntentKind) -> None:
    assert IntentBody.model_validate(payload).intent is kind


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "drive", "until": "tasks"},
        {"intent": "drive", "untill": "tasks"},
        {"intent": "exclude", "until": "tasks"},
        {"intent": "launch"},
        {},
        ["drive"],
        "drive",
    ],
)
def test_malformed_bodies_fail(payload: object) -> None:
    with pytest.raises(ValidationError):
        IntentBody.model_validate(payload)


def test_there_is_no_until_rejection_code() -> None:
    assert {code.value for code in IntentRejection} == {
        "malformed_body",
        "target_not_initiative_or_slice",
        "target_unlinked",
    }
