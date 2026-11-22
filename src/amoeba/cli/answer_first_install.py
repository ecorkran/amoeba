"""``amoeba answer-first install|uninstall``: put the hook in Claude Code's settings.

The answer-first hook (``cli.answer_first_hook``) must sit under two hook events or
neither: with only ``PreToolUse`` nothing ever releases a message and no tool runs
again. This command writes both entries, or removes both, in one atomic write of the
user's ``settings.json``, and leaves every other hook where it was.

The entries run the ``amoeba-answer-first`` executable that sits beside the running
interpreter, by absolute path, so the hook works whether Amoeba is a ``uv tool``
install or a checkout's virtualenv, and needs no ``PATH``.

A CLI-only command: no ``OperationName`` and no MCP tool, since it edits the settings
of the person at the keyboard.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Final, cast

from amoeba.cli.answer_first_hook import EVENT_PRE_TOOL_USE, EVENT_STOP
from amoeba.cli.exit_codes import EXIT_OK
from amoeba.config.home import claude_home

ANSWER_FIRST_COMMAND: Final = "answer-first"
ACTION_INSTALL: Final = "install"
ACTION_UNINSTALL: Final = "uninstall"

#: The hook's entry point (``[project.scripts]``); also how its entries are recognized.
HOOK_EXECUTABLE: Final = "amoeba-answer-first"
HOOK_TIMEOUT_SECONDS: Final = 10
HOOK_EVENTS: Final = (EVENT_PRE_TOOL_USE, EVENT_STOP)
MATCH_EVERY_TOOL: Final = "*"

#: Claude Code's own variable for a settings directory other than ``~/.claude``.
CLAUDE_CONFIG_DIR_VAR: Final = "CLAUDE_CONFIG_DIR"
SETTINGS_FILE_NAME: Final = "settings.json"


class AnswerFirstInstallError(Exception):
    """The settings file or the hook executable cannot be used; nothing was written."""


def register_answer_first(commands: Any) -> argparse.ArgumentParser:
    parser = commands.add_parser(
        ANSWER_FIRST_COMMAND,
        help="install or uninstall the answer-first hooks in Claude Code's settings",
    )
    parser.set_defaults(cli_only=ANSWER_FIRST_COMMAND)
    parser.add_argument(
        "action",
        choices=(ACTION_INSTALL, ACTION_UNINSTALL),
        help="install adds both hook entries; uninstall removes both",
    )
    return parser


def settings_path() -> Path:
    configured = os.environ.get(CLAUDE_CONFIG_DIR_VAR)
    directory = Path(configured) if configured else claude_home()
    return directory / SETTINGS_FILE_NAME


def _hook_command() -> str:
    executable = Path(sys.executable).parent / HOOK_EXECUTABLE
    if not executable.is_file():
        raise AnswerFirstInstallError(f"no {HOOK_EXECUTABLE} at {executable}")
    return shlex.quote(str(executable))


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise AnswerFirstInstallError(f"{path} is not JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise AnswerFirstInstallError(f"{path} is not a JSON object")
    return cast("dict[str, Any]", parsed)


def _is_ours(hook: object) -> bool:
    """Whether a hook entry runs the answer-first executable, however it is reached."""
    if not isinstance(hook, dict):
        return False
    command = cast("dict[str, Any]", hook).get("command")
    if not isinstance(command, str):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False  # unbalanced quotes: not a command this installer wrote
    return any(Path(word).name == HOOK_EXECUTABLE for word in words)


def _without_ours(groups: list[Any]) -> list[Any]:
    """The event's hook groups with answer-first taken out; emptied groups dropped."""
    kept: list[Any] = []
    for group in groups:
        hooks = (
            cast("dict[str, Any]", group).get("hooks")
            if isinstance(group, dict)
            else None
        )
        if not isinstance(hooks, list):
            kept.append(group)
            continue
        others = [hook for hook in cast("list[Any]", hooks) if not _is_ours(hook)]
        if others:
            kept.append({**cast("dict[str, Any]", group), "hooks": others})
    return kept


def _entry(event: str, command: str) -> dict[str, Any]:
    hook = {"type": "command", "command": command, "timeout": HOOK_TIMEOUT_SECONDS}
    if event == EVENT_PRE_TOOL_USE:
        return {"matcher": MATCH_EVERY_TOOL, "hooks": [hook]}
    return {"hooks": [hook]}


def _write(path: Path, settings: dict[str, Any]) -> None:
    """Replace the file in one step, so a reader never sees half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".amoeba-partial")
    partial.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    partial.replace(path)


def run_answer_first_install(action: str) -> int:
    """Add or remove both hook entries; the process exit code.

    Raises:
        AnswerFirstInstallError: The settings file or the executable cannot be used.
    """
    path = settings_path()
    settings = _load(path)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise AnswerFirstInstallError(f'"hooks" in {path} is not an object')
    hooks = cast("dict[str, Any]", hooks)
    command = _hook_command() if action == ACTION_INSTALL else None
    for event in HOOK_EVENTS:
        groups = hooks.get(event, [])
        if not isinstance(groups, list):
            raise AnswerFirstInstallError(f'"hooks.{event}" in {path} is not a list')
        groups = _without_ours(cast("list[Any]", groups))
        if command is not None:
            groups.append(_entry(event, command))
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    _write(path, settings)
    events = " and ".join(HOOK_EVENTS)
    if command is None:
        sys.stdout.write(f"answer-first removed from {events} in {path}\n")
    else:
        sys.stdout.write(
            f"answer-first installed under {events} in {path}\n"
            f"  command: {command}\n"
            f"  to remove: amoeba {ANSWER_FIRST_COMMAND} {ACTION_UNINSTALL}\n"
        )
    return EXIT_OK
