"""The recorded ``sq runs wait --json`` documents are what the tests say they are
(slice 223, task 2.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parents[2] / "fixtures" / "squadron"
OUTCOME_BY_FILE = {
    "wait_paused_agent_question.json": ("paused", "agent_question"),
    "wait_paused_interactive_checkpoint.json": ("paused", "interactive_checkpoint"),
    "wait_running.json": ("timed_out", None),
    "wait_completed.json": ("completed", None),
}


def _load(name: str) -> dict[str, object]:
    document: dict[str, object] = json.loads(
        (FIXTURES / name).read_text(encoding="utf-8")
    )
    return document


@pytest.mark.parametrize("name", sorted(OUTCOME_BY_FILE))
def test_each_recording_parses_with_its_outcome(name: str) -> None:
    document = _load(name)
    outcome, kind = OUTCOME_BY_FILE[name]

    assert document["outcome"] == outcome
    checkpoint = document["checkpoint"]
    if kind is None:
        assert checkpoint is None
    else:
        assert isinstance(checkpoint, dict)
        assert checkpoint["kind"] == kind


def test_the_pause_recording_has_kind_paused_at_and_question() -> None:
    checkpoint = _load("wait_paused_agent_question.json")["checkpoint"]

    assert isinstance(checkpoint, dict)
    assert checkpoint["kind"] == "agent_question"
    assert isinstance(checkpoint["paused_at"], str)
    assert isinstance(checkpoint["question"], str)
    assert checkpoint["question"].strip()
