"""``paused_at_text`` returns what ``sq runs wait --json`` printed (slice 223, D1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amoeba.upstream.squadron.run_outcome import RunOutcomeDocument

FIXTURES = Path(__file__).parents[2] / "fixtures" / "squadron"
PAUSED = [
    "wait_paused_agent_question.json",
    "wait_paused_interactive_checkpoint.json",
    "resume_lock_before.json",
]


@pytest.mark.parametrize("name", PAUSED)
def test_the_text_is_the_recorded_text_exactly(name: str) -> None:
    raw = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    document = RunOutcomeDocument.model_validate(raw)

    assert document.checkpoint is not None
    assert document.checkpoint.paused_at_text == raw["checkpoint"]["paused_at"]


def test_no_paused_at_is_none() -> None:
    raw = json.loads((FIXTURES / "wait_running.json").read_text(encoding="utf-8"))
    document = RunOutcomeDocument.model_validate(
        {**raw, "checkpoint": {"kind": "other"}}
    )

    assert document.checkpoint is not None
    assert document.checkpoint.paused_at_text is None
