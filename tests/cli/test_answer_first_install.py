"""``amoeba answer-first install|uninstall``: both hook entries, or neither."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from amoeba.cli.answer_first_hook import EVENT_PRE_TOOL_USE, EVENT_STOP
from amoeba.cli.answer_first_install import (
    CLAUDE_CONFIG_DIR_VAR,
    HOOK_EXECUTABLE,
    HOOK_TIMEOUT_SECONDS,
    SETTINGS_FILE_NAME,
)
from amoeba.cli.main import EXIT_ERROR, EXIT_OK, main

OTHER_HOOK = {"type": "command", "command": "node /opt/monitor/hook-handler.js"}
#: The shape of the PM's real settings file: another tool's hooks under both events.
EXISTING_SETTINGS: dict[str, Any] = {
    "model": "fable",
    "hooks": {
        EVENT_PRE_TOOL_USE: [{"matcher": "*", "hooks": [OTHER_HOOK]}],
        EVENT_STOP: [
            {"matcher": "*", "hooks": [OTHER_HOOK]},
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "uv run --quiet --project /repo amoeba stand-in",
                        "timeout": 120,
                    }
                ]
            },
        ],
        "SessionStart": [{"hooks": [OTHER_HOOK]}],
    },
}
HOOK_PATH = str(Path(sys.executable).parent / HOOK_EXECUTABLE)


@pytest.fixture
def settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_VAR, str(tmp_path))
    return tmp_path / SETTINGS_FILE_NAME


def _write(settings_file: Path, settings: object) -> None:
    settings_file.write_text(json.dumps(settings), encoding="utf-8")


def _commands(settings_file: Path, event: str) -> list[str]:
    settings = json.loads(settings_file.read_text(encoding="utf-8"))
    return [
        hook["command"]
        for group in settings["hooks"].get(event, [])
        for hook in group["hooks"]
    ]


def test_install_adds_both_entries_beside_the_hooks_already_there(
    settings_file: Path,
) -> None:
    _write(settings_file, EXISTING_SETTINGS)

    assert main(["answer-first", "install"]) == EXIT_OK

    settings = json.loads(settings_file.read_text(encoding="utf-8"))
    assert settings["model"] == "fable"
    assert settings["hooks"]["SessionStart"] == [{"hooks": [OTHER_HOOK]}]
    assert _commands(settings_file, EVENT_PRE_TOOL_USE) == [
        OTHER_HOOK["command"],
        HOOK_PATH,
    ]
    assert _commands(settings_file, EVENT_STOP) == [
        OTHER_HOOK["command"],
        "uv run --quiet --project /repo amoeba stand-in",
        HOOK_PATH,
    ]
    assert settings["hooks"][EVENT_PRE_TOOL_USE][-1] == {
        "matcher": "*",
        "hooks": [
            {"type": "command", "command": HOOK_PATH, "timeout": HOOK_TIMEOUT_SECONDS}
        ],
    }


def test_install_twice_leaves_one_entry_per_event(settings_file: Path) -> None:
    _write(settings_file, EXISTING_SETTINGS)

    main(["answer-first", "install"])
    main(["answer-first", "install"])

    assert _commands(settings_file, EVENT_PRE_TOOL_USE).count(HOOK_PATH) == 1
    assert _commands(settings_file, EVENT_STOP).count(HOOK_PATH) == 1


def test_install_replaces_an_entry_written_by_hand_in_the_checkout_form(
    settings_file: Path,
) -> None:
    by_hand = f"uv run --quiet --project /repo {HOOK_EXECUTABLE}"
    _write(
        settings_file,
        {
            "hooks": {
                EVENT_PRE_TOOL_USE: [
                    {"matcher": "*", "hooks": [{"type": "command", "command": by_hand}]}
                ]
            }
        },
    )

    main(["answer-first", "install"])

    assert _commands(settings_file, EVENT_PRE_TOOL_USE) == [HOOK_PATH]
    assert _commands(settings_file, EVENT_STOP) == [HOOK_PATH]


def test_install_creates_the_settings_file_when_there_is_none(
    settings_file: Path,
) -> None:
    assert main(["answer-first", "install"]) == EXIT_OK

    assert _commands(settings_file, EVENT_PRE_TOOL_USE) == [HOOK_PATH]
    assert _commands(settings_file, EVENT_STOP) == [HOOK_PATH]


def test_uninstall_removes_both_entries_and_nothing_else(settings_file: Path) -> None:
    _write(settings_file, EXISTING_SETTINGS)
    main(["answer-first", "install"])

    assert main(["answer-first", "uninstall"]) == EXIT_OK

    assert json.loads(settings_file.read_text(encoding="utf-8")) == EXISTING_SETTINGS


def test_uninstall_drops_an_event_left_with_no_hooks(settings_file: Path) -> None:
    main(["answer-first", "install"])

    main(["answer-first", "uninstall"])

    assert json.loads(settings_file.read_text(encoding="utf-8")) == {"hooks": {}}


@pytest.mark.parametrize(
    "content",
    ["[]", "{not json", '{"hooks": []}', '{"hooks": {"Stop": {}}}'],
)
def test_a_settings_file_it_cannot_read_is_an_error_and_is_left_alone(
    settings_file: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    settings_file.write_text(content, encoding="utf-8")

    assert main(["answer-first", "install"]) == EXIT_ERROR

    assert settings_file.read_text(encoding="utf-8") == content
    assert "AnswerFirstInstallError" in capsys.readouterr().err


def test_install_says_where_it_wrote_and_how_to_remove_it(
    settings_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["answer-first", "install"])

    out = capsys.readouterr().out
    assert str(settings_file) in out
    assert "amoeba answer-first uninstall" in out


def test_the_command_is_listed_in_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "answer-first" in capsys.readouterr().out
