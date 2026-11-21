"""Claude Code session transcript entries, for tests of code that reads a transcript.

Each carries the fields Claude Code wrote in a real session transcript on 2026-11-21
(one JSON object per line, each content block its own entry).
"""

from __future__ import annotations

import json
from typing import Any


def pm_prompt(text: str, uuid: str) -> dict[str, Any]:
    """A message the PM typed that starts a turn."""
    return {
        "type": "user",
        "uuid": uuid,
        "isSidechain": False,
        "promptSource": "sdk",
        "turnOrigin": "human",
        "origin": {"kind": "human"},
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def pm_mid_turn(text: str, uuid: str) -> dict[str, Any]:
    """A message the PM sent while the agent was working."""
    return {
        "type": "attachment",
        "uuid": uuid,
        "isSidechain": False,
        "attachment": {
            "type": "queued_command",
            "prompt": [{"type": "text", "text": text}],
            "commandMode": "prompt",
            "origin": {"kind": "human"},
        },
    }


def agent(block: dict[str, Any]) -> dict[str, Any]:
    """One content block the agent produced."""
    return {
        "type": "assistant",
        "isSidechain": False,
        "message": {"role": "assistant", "content": [block]},
    }


def stop_block(reason: str) -> dict[str, Any]:
    """A stop hook's refusal to let the turn end."""
    return {
        "type": "attachment",
        "isSidechain": False,
        "attachment": {
            "type": "hook_blocking_error",
            "hookName": "Stop",
            "hookEvent": "Stop",
            "blockingError": {"blockingError": reason, "command": "a command"},
        },
    }


TEXT = agent({"type": "text", "text": "Here is the answer."})
THINKING = agent({"type": "thinking", "thinking": "hmm"})
TOOL_USE = agent({"type": "tool_use", "id": "t1", "name": "Bash", "input": {}})
TOOL_RESULT: dict[str, Any] = {
    "type": "user",
    "isSidechain": False,
    "message": {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
    },
}
HOOK_FEEDBACK: dict[str, Any] = {
    "type": "user",
    "isMeta": True,
    "message": {"role": "user", "content": "Stop hook feedback: carry on."},
}
PEER_MESSAGE: dict[str, Any] = {
    "type": "user",
    "isMeta": True,
    "turnOrigin": "peer",
    "origin": {"kind": "peer", "name": "sq"},
    "message": {"role": "user", "content": "Another Claude session sent a message"},
}
TASK_NOTIFICATION: dict[str, Any] = {
    "type": "user",
    "turnOrigin": "task_notification",
    "origin": {"kind": "task-notification"},
    "message": {"role": "user", "content": "<task-notification>done"},
}
SLASH_COMMAND: dict[str, Any] = {
    "type": "user",
    "uuid": "slash-1",
    "turnOrigin": "human",
    "origin": {"kind": "human"},
    "message": {
        "role": "user",
        "content": "<command-message>sq:summary</command-message>",
    },
}
INTERRUPTED: dict[str, Any] = {
    "type": "user",
    "message": {
        "role": "user",
        "content": [{"type": "text", "text": "[Request interrupted by user]"}],
    },
}


def transcript_lines(*entries: dict[str, Any]) -> list[str]:
    """``entries`` as transcript lines, oldest first, in Claude Code's compact form."""
    return [json.dumps(entry, separators=(",", ":")) for entry in entries]


def newest_first(*entries: dict[str, Any]) -> list[str]:
    """``entries`` (given oldest first) as transcript lines, newest first."""
    return list(reversed(transcript_lines(*entries)))
