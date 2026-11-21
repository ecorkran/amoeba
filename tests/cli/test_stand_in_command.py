"""``amoeba stand-in``: the Stop hook's input, decision and failure paths."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from amoeba.cli import stand_in_command
from amoeba.cli.stand_in_command import (
    StandInError,
    closing_message,
    run_stand_in,
)
from amoeba.operations.stand_in import CHILD_ENV_VAR, REASON_PREFIX, Judgement, Verdict

HANDOFF = "Want me to run the task review too?"


def _run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    hook_input: dict[str, Any],
) -> tuple[int, str, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
    code = run_stand_in()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _stub_model(monkeypatch: pytest.MonkeyPatch, judgement: Judgement) -> list[str]:
    prompts: list[str] = []

    def fake(prompt: str) -> Judgement:
        prompts.append(prompt)
        return judgement

    monkeypatch.setattr(stand_in_command, "ask_model", fake)
    monkeypatch.setattr(stand_in_command, "gather_standing", lambda: "")
    return prompts


def test_a_settled_handoff_blocks_the_stop_with_the_instruction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    _stub_model(monkeypatch, Judgement(Verdict.SETTLED, "Run it."))
    code, out, _ = _run(
        monkeypatch,
        capsys,
        {
            "cwd": str(tmp_path),
            "last_assistant_message": HANDOFF,
        },
    )
    assert code == 0
    assert json.loads(out) == {"decision": "block", "reason": REASON_PREFIX + "Run it."}


def test_a_question_for_the_pm_lets_the_turn_end(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    _stub_model(monkeypatch, Judgement(Verdict.FOR_PM, "It spends money."))
    code, out, _ = _run(
        monkeypatch,
        capsys,
        {
            "cwd": str(tmp_path),
            "last_assistant_message": HANDOFF,
        },
    )
    assert (code, out) == (0, "")


def test_no_handoff_and_a_second_stop_make_no_model_call(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    prompts = _stub_model(monkeypatch, Judgement(Verdict.SETTLED, "x"))
    _run(monkeypatch, capsys, {"cwd": str(tmp_path), "last_assistant_message": "Done."})
    _run(
        monkeypatch,
        capsys,
        {
            "cwd": str(tmp_path),
            "last_assistant_message": HANDOFF,
            "stop_hook_active": True,
        },
    )
    assert prompts == []


def test_the_judges_own_session_is_never_judged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    prompts = _stub_model(monkeypatch, Judgement(Verdict.SETTLED, "x"))
    monkeypatch.setenv(CHILD_ENV_VAR, "1")
    code, out, _ = _run(
        monkeypatch,
        capsys,
        {
            "cwd": str(tmp_path),
            "last_assistant_message": HANDOFF,
        },
    )
    assert (code, out, prompts) == (0, "", [])


def test_a_failed_model_call_is_one_stderr_line_and_exit_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def fail(prompt: str) -> Judgement:
        raise StandInError("the model call timed out")

    monkeypatch.setattr(stand_in_command, "ask_model", fail)
    monkeypatch.setattr(stand_in_command, "gather_standing", lambda: "")
    code, out, err = _run(
        monkeypatch,
        capsys,
        {
            "cwd": str(tmp_path),
            "last_assistant_message": HANDOFF,
        },
    )
    assert (code, out) == (1, "")
    assert "timed out" in err


def test_the_closing_message_comes_from_the_transcript_when_not_given(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "session.jsonl"
    lines = [
        {"type": "user", "message": {"content": "hi"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "a"}]}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Bash"},
                    {"type": "text", "text": HANDOFF},
                ]
            },
        },
    ]
    transcript.write_text("\n".join(json.dumps(line) for line in lines) + "\n{part")
    assert closing_message({"transcript_path": str(transcript)}) == HANDOFF
