"""``amoeba stand-in`` in a turn that the answer-first hook kept going.

Answer-first keeps a turn going once after each PM message, so the PM sees the reply.
That is not a stand-in decision: the end of the work that follows is still judged.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from transcript_entries import (
    HOOK_FEEDBACK,
    TEXT,
    TOOL_RESULT,
    TOOL_USE,
    pm_prompt,
    stop_block,
    transcript_lines,
)

from amoeba.cli import stand_in_command
from amoeba.cli.answer_first_hook import RESUME
from amoeba.cli.stand_in_command import run_stand_in
from amoeba.operations.stand_in import CHILD_ENV_VAR, REASON_PREFIX, Judgement, Verdict

HANDOFF = "Want me to run the task review too?"


def _judged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *last_stop: dict[str, Any],
) -> bool:
    """Whether the stand-in asks its model at a stop that follows ``last_stop``."""
    transcript = tmp_path / "session.jsonl"
    entries = (
        pm_prompt("go", "p1"),
        TEXT,
        HOOK_FEEDBACK,
        *last_stop,
        TOOL_USE,
        TOOL_RESULT,
    )
    transcript.write_text("\n".join(transcript_lines(*entries)), encoding="utf-8")
    prompts: list[str] = []

    def fake(prompt: str) -> Judgement:
        prompts.append(prompt)
        return Judgement(Verdict.SETTLED, "Run it.")

    monkeypatch.delenv(CHILD_ENV_VAR, raising=False)
    monkeypatch.setattr(stand_in_command, "ask_model", fake)
    monkeypatch.setattr(stand_in_command, "gather_standing", lambda: "")
    hook_input = {
        "cwd": str(tmp_path),
        "last_assistant_message": HANDOFF,
        "stop_hook_active": True,
        "transcript_path": str(transcript),
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
    assert run_stand_in() == 0
    return bool(prompts)


def test_a_turn_kept_going_only_by_answer_first_is_still_judged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert _judged(monkeypatch, tmp_path, stop_block(RESUME))


def test_a_turn_the_stand_in_kept_going_is_not_judged_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert not _judged(monkeypatch, tmp_path, stop_block(REASON_PREFIX + "Run it."))


def test_a_stop_both_hooks_refused_counts_as_the_stand_ins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    both = (stop_block(RESUME), stop_block(REASON_PREFIX + "Run it."))
    joined = stop_block(RESUME + "\n" + REASON_PREFIX + "Run it.")

    assert not _judged(monkeypatch, tmp_path, *both)
    assert not _judged(monkeypatch, tmp_path, joined)


def test_a_turn_no_stop_hook_kept_going_is_not_judged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert not _judged(monkeypatch, tmp_path)
