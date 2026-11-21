"""``amoeba-answer-first``: the PM sees a reply before any tool runs.

One command, installed in Claude Code under two hook events. It reads the hook's JSON
on stdin and acts on its ``hook_event_name``:

- ``PreToolUse`` (before every tool call): when the PM has sent a message that has not
  been released, exit 2 with the reason on stderr. Claude Code refuses the tool call
  and shows the agent the reason: reply in text and end the turn.
- ``Stop`` (when a turn ends): when the agent has replied to an unreleased PM message,
  record the release and print a ``block`` decision, so the PM sees the reply and the
  agent goes straight on with the work. Each PM message is released once, so a turn can
  be kept going at most once per message.

The two halves need each other. With only ``PreToolUse`` installed nothing ever
releases a message and no tool runs again; ``docs/answer-first.md`` gives both entries.

The release is one small file per session, ``<state home>/answer-first/<session id>``,
holding the id of the last PM message released. Files untouched for
``STATE_KEEP_DAYS`` are deleted whenever one is written.

It has its own entry point, apart from ``amoeba``, and imports only the standard
library and three small modules, because it runs before every tool call in every
session. A failure (unreadable input or transcript) is one line on stderr and exit 1,
which Claude Code shows without refusing anything: the hook never blocks work on its
own fault.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Final, cast

from amoeba.config.home import AmoebaHomeError, state_home
from amoeba.operations.answer_first import (
    ANSWER_FIRST_PREFIX,
    PmMessage,
    latest_pm_message,
)

# Set in the stand-in's own judging session, which no PM is reading.
from amoeba.operations.stand_in import CHILD_ENV_VAR

EVENT_PRE_TOOL_USE: Final = "PreToolUse"
EVENT_STOP: Final = "Stop"
#: Present in the hook's input when the tool call is made inside a subagent.
SUBAGENT_FIELD: Final = "agent_id"

STATE_DIR_NAME: Final = "answer-first"
STATE_KEEP_DAYS: Final = 30
SECONDS_PER_DAY: Final = 86_400

EXIT_ALLOW: Final = 0
EXIT_FAILED: Final = 1
#: The exit code Claude Code reads as "refuse this tool call and tell the agent why".
EXIT_REFUSE: Final = 2

REFUSAL_NO_REPLY: Final = ANSWER_FIRST_PREFIX + (
    "the PM sent a message and has not seen a reply. Do not call tools yet. Write "
    "your reply in text (the answer, or what you understood and what you will do), "
    "then end your turn. You will be put straight back to work once he has it."
)
REFUSAL_NOT_ENDED: Final = ANSWER_FIRST_PREFIX + (
    "you have replied to the PM but he only sees it when your turn ends. End your "
    "turn now, with no tool call. You will be put straight back to work."
)
RESUME: Final = ANSWER_FIRST_PREFIX + (
    "the PM has your reply. If his message left work to do, do it now. If nothing "
    "is left to do, end your turn without repeating the reply."
)


class AnswerFirstError(Exception):
    """The hook's input could not be used; nothing is refused."""


def _text_field(hook_input: dict[str, Any], name: str) -> str:
    value = hook_input.get(name)
    if not isinstance(value, str) or not value:
        raise AnswerFirstError(f"the hook input has no {name}")
    return value


def _state_file(hook_input: dict[str, Any]) -> Path:
    session_id = _text_field(hook_input, "session_id")
    if not session_id.replace("-", "").replace("_", "").isalnum():
        raise AnswerFirstError(f"session_id {session_id!r} cannot name a file")
    return state_home() / STATE_DIR_NAME / session_id


def _released(state_file: Path) -> str | None:
    """The id of the last PM message released in this session, if any."""
    if not state_file.is_file():
        return None
    return state_file.read_text(encoding="utf-8").strip()


def _release(state_file: Path, message_id: str) -> None:
    """Record the release, and delete the files of sessions long finished."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(message_id + "\n", encoding="utf-8")
    oldest_kept = time.time() - STATE_KEEP_DAYS * SECONDS_PER_DAY
    for other in state_file.parent.iterdir():
        if other.is_file() and other.stat().st_mtime < oldest_kept:
            other.unlink(missing_ok=True)


def _pm_message(hook_input: dict[str, Any]) -> PmMessage | None:
    transcript = Path(_text_field(hook_input, "transcript_path"))
    lines = transcript.read_text(encoding="utf-8").splitlines()
    lines.reverse()
    return latest_pm_message(lines)


def _before_tool(hook_input: dict[str, Any]) -> int:
    if hook_input.get(SUBAGENT_FIELD):
        return EXIT_ALLOW  # a subagent works for the agent and cannot reply to the PM
    message = _pm_message(hook_input)
    if message is None or _released(_state_file(hook_input)) == message.message_id:
        return EXIT_ALLOW
    refusal = REFUSAL_NOT_ENDED if message.replied else REFUSAL_NO_REPLY
    sys.stderr.write(refusal + "\n")
    return EXIT_REFUSE


def _ended_with_text(hook_input: dict[str, Any]) -> bool:
    """Whether the turn now ending closed with text, by the hook's own field.

    The transcript is written a little behind the conversation, so the closing message
    may not be in it yet.
    """
    closing = hook_input.get("last_assistant_message")
    return isinstance(closing, str) and bool(closing.strip())


def _at_stop(hook_input: dict[str, Any]) -> int:
    message = _pm_message(hook_input)
    if message is None or not (message.replied or _ended_with_text(hook_input)):
        return EXIT_ALLOW
    state_file = _state_file(hook_input)
    if _released(state_file) == message.message_id:
        return EXIT_ALLOW
    _release(state_file, message.message_id)
    sys.stdout.write(json.dumps({"decision": "block", "reason": RESUME}))
    return EXIT_ALLOW


def run_answer_first() -> int:
    """Read the hook's input and act on its event; the process exit code."""
    if os.environ.get(CHILD_ENV_VAR):
        return EXIT_ALLOW
    try:
        parsed: object = json.loads(sys.stdin.read())
        if not isinstance(parsed, dict):
            raise AnswerFirstError("the hook input is not a JSON object")
        hook_input = cast("dict[str, Any]", parsed)
        event = _text_field(hook_input, "hook_event_name")
        if event == EVENT_PRE_TOOL_USE:
            return _before_tool(hook_input)
        if event == EVENT_STOP:
            return _at_stop(hook_input)
        raise AnswerFirstError(f"not installed for the {event} event")
    except (AnswerFirstError, AmoebaHomeError, OSError, ValueError) as error:
        # The process boundary: report once and refuse nothing. ValueError covers
        # input that is not JSON and a transcript that is not UTF-8.
        sys.stderr.write(f"amoeba-answer-first: {error}\n")
        return EXIT_FAILED


def main() -> None:
    sys.exit(run_answer_first())
