"""``amoeba-answer-first``: refuse tools until the PM has a reply, then release once."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from transcript_entries import (
    TEXT,
    THINKING,
    TOOL_RESULT,
    TOOL_USE,
    pm_mid_turn,
    pm_prompt,
    transcript_lines,
)

from amoeba.cli.answer_first_hook import (
    EVENT_PRE_TOOL_USE,
    EVENT_STOP,
    EXIT_ALLOW,
    EXIT_FAILED,
    EXIT_REFUSE,
    REFUSAL_NO_REPLY,
    REFUSAL_NOT_ENDED,
    RESUME,
    STATE_DIR_NAME,
    STATE_KEEP_DAYS,
    run_answer_first,
)
from amoeba.config.home import state_home
from amoeba.operations.stand_in import CHILD_ENV_VAR

SESSION = "4d6b3bed-fb21-45e0-9a2e-07603d3478cd"
RESUME_DECISION = {"decision": "block", "reason": RESUME}


class Session:
    """One session's transcript file, and the hook run against it."""

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self.transcript = tmp_path / "session.jsonl"
        self.transcript.write_text("", encoding="utf-8")
        self._monkeypatch = monkeypatch
        self._capsys = capsys
        monkeypatch.delenv(CHILD_ENV_VAR, raising=False)

    def add(self, *entries: dict[str, Any]) -> None:
        with self.transcript.open("a", encoding="utf-8") as transcript:
            transcript.writelines(line + "\n" for line in transcript_lines(*entries))

    def run(self, event: str, session: str = SESSION) -> tuple[int, str, str]:
        return self.run_raw(
            json.dumps(
                {
                    "hook_event_name": event,
                    "session_id": session,
                    "transcript_path": str(self.transcript),
                }
            )
        )

    def run_raw(self, stdin: str) -> tuple[int, str, str]:
        self._monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        code = run_answer_first()
        captured = self._capsys.readouterr()
        return code, captured.out, captured.err.strip()

    def tool(self) -> tuple[int, str, str]:
        return self.run(EVENT_PRE_TOOL_USE)

    def stop(self) -> tuple[int, str, str]:
        return self.run(EVENT_STOP)


@pytest.fixture
def session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> Session:
    return Session(tmp_path, monkeypatch, capsys)


ALLOWED = (EXIT_ALLOW, "", "")


def test_a_tool_call_before_any_reply_is_refused(session: Session) -> None:
    session.add(pm_prompt("what is breaking?", "p1"), THINKING)

    assert session.tool() == (EXIT_REFUSE, "", REFUSAL_NO_REPLY)


def test_a_tool_call_after_a_reply_is_refused_until_the_turn_ends(
    session: Session,
) -> None:
    session.add(pm_prompt("what is breaking?", "p1"), TEXT)

    assert session.tool() == (EXIT_REFUSE, "", REFUSAL_NOT_ENDED)


def test_ending_the_turn_with_a_reply_keeps_it_going_and_frees_the_tools(
    session: Session,
) -> None:
    session.add(pm_prompt("go ahead and rework the hook", "p1"), TEXT)

    code, out, err = session.stop()

    assert (code, json.loads(out), err) == (EXIT_ALLOW, RESUME_DECISION, "")
    session.add(THINKING)
    assert session.tool() == ALLOWED
    session.add(TOOL_USE, TOOL_RESULT, TEXT)
    assert session.tool() == ALLOWED


def test_a_turn_is_kept_going_once_per_pm_message(session: Session) -> None:
    session.add(pm_prompt("go", "p1"), TEXT)
    session.stop()
    session.add(TOOL_USE, TOOL_RESULT, TEXT)

    assert session.stop() == ALLOWED


def test_ending_a_turn_with_no_reply_releases_nothing(session: Session) -> None:
    session.add(pm_prompt("go", "p1"), THINKING)

    assert session.stop() == ALLOWED
    assert session.tool() == (EXIT_REFUSE, "", REFUSAL_NO_REPLY)


def test_a_message_sent_mid_turn_closes_the_tools_until_it_is_answered(
    session: Session,
) -> None:
    session.add(pm_prompt("go", "p1"), TEXT)
    session.stop()
    session.add(TOOL_USE, TOOL_RESULT, pm_mid_turn("wait, what is that?", "p2"))

    assert session.tool() == (EXIT_REFUSE, "", REFUSAL_NO_REPLY)
    session.add(TEXT)
    assert json.loads(session.stop()[1]) == RESUME_DECISION
    assert session.tool() == ALLOWED


def test_the_pms_next_prompt_closes_the_tools_again(session: Session) -> None:
    session.add(pm_prompt("go", "p1"), TEXT)
    session.stop()
    session.add(pm_prompt("and now this", "p2"))

    assert session.tool() == (EXIT_REFUSE, "", REFUSAL_NO_REPLY)


def test_a_session_with_no_pm_message_is_left_alone(session: Session) -> None:
    session.add(THINKING, TEXT)

    assert session.tool() == ALLOWED
    assert session.stop() == ALLOWED


def test_one_sessions_release_does_not_free_another(session: Session) -> None:
    session.add(pm_prompt("go", "p1"), TEXT)
    session.stop()

    assert session.run(EVENT_PRE_TOOL_USE, session="another-session")[0] == EXIT_REFUSE


def test_releases_of_sessions_long_finished_are_deleted(session: Session) -> None:
    state_dir = state_home() / STATE_DIR_NAME
    state_dir.mkdir(parents=True)
    old, recent = state_dir / "old-session", state_dir / "recent-session"
    for path in (old, recent):
        path.write_text("p0\n", encoding="utf-8")
    long_ago = time.time() - (STATE_KEEP_DAYS + 1) * 86_400
    os.utime(old, (long_ago, long_ago))
    session.add(pm_prompt("go", "p1"), TEXT)

    session.stop()

    assert sorted(path.name for path in state_dir.iterdir()) == [
        SESSION,
        "recent-session",
    ]


@pytest.mark.parametrize(
    ("stdin", "said"),
    [
        ("not json", "amoeba-answer-first:"),
        ('["a list"]', "not a JSON object"),
        ("{}", "no hook_event_name"),
        (json.dumps({"hook_event_name": "SessionStart"}), "SessionStart event"),
        (json.dumps({"hook_event_name": "PreToolUse"}), "no transcript_path"),
        (
            json.dumps(
                {"hook_event_name": "Stop", "transcript_path": "/nonexistent/s.jsonl"}
            ),
            "nonexistent",
        ),
    ],
)
def test_a_hook_fault_is_one_line_and_refuses_nothing(
    session: Session, stdin: str, said: str
) -> None:
    code, out, err = session.run_raw(stdin)

    assert (code, out) == (EXIT_FAILED, "")
    assert said in err
    assert "\n" not in err


@pytest.mark.parametrize("bad_session", ["", "../../etc/passwd", "a b"])
def test_a_session_id_that_cannot_name_a_file_is_a_fault(
    session: Session, bad_session: str
) -> None:
    session.add(pm_prompt("go", "p1"), TEXT)

    assert session.run(EVENT_STOP, session=bad_session)[0] == EXIT_FAILED
    assert not (state_home() / STATE_DIR_NAME).exists()


def test_a_tool_call_inside_a_subagent_is_never_refused(session: Session) -> None:
    session.add(pm_prompt("go", "p1"), THINKING)
    hook_input = {
        "hook_event_name": EVENT_PRE_TOOL_USE,
        "session_id": SESSION,
        "transcript_path": str(session.transcript),
        "agent_id": "a30ca2c61d9cdf208",
    }

    assert session.run_raw(json.dumps(hook_input)) == ALLOWED


def test_a_reply_not_yet_in_the_transcript_still_releases_at_the_stop(
    session: Session,
) -> None:
    session.add(pm_prompt("go", "p1"), THINKING)
    hook_input = {
        "hook_event_name": EVENT_STOP,
        "session_id": SESSION,
        "transcript_path": str(session.transcript),
        "last_assistant_message": "Here is the answer.",
    }

    assert json.loads(session.run_raw(json.dumps(hook_input))[1]) == RESUME_DECISION
    assert session.tool() == ALLOWED


def test_the_stand_ins_own_judging_session_is_left_alone(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session.add(pm_prompt("judge this", "p1"), THINKING)
    monkeypatch.setenv(CHILD_ENV_VAR, "1")

    assert session.tool() == ALLOWED
    assert session.stop() == ALLOWED


def test_the_hook_starts_without_importing_the_rest_of_amoeba() -> None:
    """It runs before every tool call, so it must not pull in the store or the CLI."""
    light = {
        "amoeba.cli",
        "amoeba.cli.answer_first_hook",
        "amoeba.config",
        "amoeba.config.home",
        "amoeba.operations",
        "amoeba.operations.answer_first",
        "amoeba.operations.stand_in",
    }
    script = (
        "import sys; import amoeba.cli.answer_first_hook; "
        "print('\\n'.join(m for m in sys.modules if m.startswith('amoeba.')))"
    )

    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )

    assert set(result.stdout.split()) <= light
