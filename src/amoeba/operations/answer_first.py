"""Answer first: what a session transcript says about the PM's last message.

The rule the ``amoeba-answer-first`` hooks enforce: after the PM sends a message, the
agent replies in text and ends its turn, so the PM sees the reply, before any tool
runs. This module reads the transcript for the two facts that rule needs: which entry
is the PM's latest message, and whether the agent has written text since.

It reads the lines of a Claude Code session transcript (JSONL, one entry per line, each
content block its own entry) and imports only the standard library, because the hook
runs before every tool call and must start fast.

Shapes read, as Claude Code wrote them on 2026-11-21. The format has no published
contract, so an entry in any other shape is passed over, and a transcript with no
recognisable PM message means the hooks do nothing:

- A PM prompt that starts a turn:
  ``{"type": "user", "uuid": ..., "origin": {"kind": "human"}, ...}``.
- A PM message sent while the agent works:
  ``{"type": "attachment", "uuid": ..., "attachment": {"type": "queued_command",
  "origin": {"kind": "human"}, ...}}``.
- The agent's text: ``{"type": "assistant", "message": {"content": [{"type": "text",
  "text": ...}]}}``.
- A stop hook's refusal to let a turn end: ``{"type": "attachment", "attachment":
  {"type": "hook_blocking_error", "hookEvent": "Stop",
  "blockingError": {"blockingError": <reason>}}}``.

Not PM messages: tool results, hook feedback, task notifications and peer messages
(their ``origin.kind`` is not ``human``, or they have no ``origin``), and a slash
command, whose own instructions say what its output must be.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Final, cast

ENTRY_USER: Final = "user"
ENTRY_ASSISTANT: Final = "assistant"
ENTRY_ATTACHMENT: Final = "attachment"
ORIGIN_HUMAN: Final = "human"
ATTACHMENT_QUEUED_MESSAGE: Final = "queued_command"
ATTACHMENT_HOOK_BLOCK: Final = "hook_blocking_error"
HOOK_EVENT_STOP: Final = "Stop"
BLOCK_TEXT: Final = "text"
#: A slash command's prompt is a string that opens with a Claude Code command tag.
SLASH_COMMAND_PREFIX: Final = "<command-"
#: A text block that opens with a tag the harness wrote (an opened file, a reminder,
#: tool instructions) and not a command the PM ran: not his words.
HARNESS_BLOCK: Final = re.compile(r"\s*<(?!command-)[a-z][a-z_-]*[\s>]")
#: Opens every reason the answer-first hooks give, so the stand-in can tell a turn
#: that answer-first kept going from one it kept going itself.
ANSWER_FIRST_PREFIX: Final = "Amoeba answer-first: "


@dataclass(frozen=True)
class PmMessage:
    """The PM's latest message in a transcript."""

    #: The transcript entry's ``uuid``: what its release is recorded under.
    message_id: str
    #: Whether the agent has written text in the main conversation since.
    replied: bool


def _dict(value: object) -> dict[str, Any]:
    """``value`` as a dict, or an empty one for any other shape."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _entries(newest_first: Iterable[str]) -> Iterator[dict[str, Any]]:
    for line in newest_first:
        try:
            entry = _dict(json.loads(line))
        except json.JSONDecodeError:
            continue  # a partly written last line; the entries before it still count
        if entry and not entry.get("isSidechain"):  # not a subagent's conversation
            yield entry


def _from_human(holder: dict[str, Any]) -> bool:
    return _dict(holder.get("origin")).get("kind") == ORIGIN_HUMAN


def is_pm_message(entry: dict[str, Any]) -> bool:
    """Whether this entry is something the PM typed to the agent."""
    kind = entry.get("type")
    if kind == ENTRY_ATTACHMENT:
        attachment = _dict(entry.get("attachment"))
        queued = attachment.get("type") == ATTACHMENT_QUEUED_MESSAGE
        return queued and _from_human(attachment)
    if kind != ENTRY_USER or not _from_human(entry):
        return False
    content = _dict(entry.get("message")).get("content")
    return not (isinstance(content, str) and content.startswith(SLASH_COMMAND_PREFIX))


def is_agent_text(entry: dict[str, Any]) -> bool:
    """Whether this entry is text the agent wrote."""
    if entry.get("type") != ENTRY_ASSISTANT:
        return False
    content = _dict(entry.get("message")).get("content")
    if not isinstance(content, list):
        return False
    for block in cast("list[object]", content):
        typed = _dict(block)
        text = typed.get("text")
        if typed.get("type") == BLOCK_TEXT and isinstance(text, str) and text.strip():
            return True
    return False


def latest_pm_message(newest_first: Iterable[str]) -> PmMessage | None:
    """The PM's latest message, read from the transcript's end backwards.

    ``None`` when the transcript holds no PM message, or holds one with no ``uuid`` to
    record a release under.
    """
    replied = False
    for entry in _entries(newest_first):
        if is_agent_text(entry):
            replied = True
        elif is_pm_message(entry):
            message_id = entry.get("uuid")
            if isinstance(message_id, str) and message_id:
                return PmMessage(message_id, replied)
            return None
    return None


def _text_blocks(content: object) -> list[str]:
    """The texts in a message's content: the string itself, or its text blocks."""
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    texts = (_dict(block) for block in cast("list[object]", content))
    return [
        block["text"]
        for block in texts
        if block.get("type") == BLOCK_TEXT and isinstance(block.get("text"), str)
    ]


def _pm_words(entry: dict[str, Any]) -> str | None:
    """What the PM typed or ran in this entry; ``None`` when the entry is not his."""
    kind = entry.get("type")
    if kind == ENTRY_ATTACHMENT:
        attachment = _dict(entry.get("attachment"))
        if attachment.get("type") != ATTACHMENT_QUEUED_MESSAGE:
            return None
        if not _from_human(attachment):
            return None
        content = attachment.get("prompt")
    elif kind == ENTRY_USER and _from_human(entry):
        content = _dict(entry.get("message")).get("content")
    else:
        return None
    words = [
        text.strip()
        for text in _text_blocks(content)
        if text.strip() and not HARNESS_BLOCK.match(text)
    ]
    return "\n".join(words) or None


def recent_pm_requests(newest_first: Iterable[str], limit: int) -> list[str]:
    """The PM's last ``limit`` messages and slash commands, oldest first.

    Unlike ``latest_pm_message`` this counts a slash command: it is not a message to
    reply to, but it is what he asked the session for.
    """
    requests: list[str] = []
    for entry in _entries(newest_first):
        words = _pm_words(entry)
        if words is not None:
            requests.append(words)
            if len(requests) == limit:
                break
    requests.reverse()
    return requests


def _stop_block_reason(entry: dict[str, Any]) -> str | None:
    """The reason a stop hook gave for refusing a turn's end, if this entry is one."""
    attachment = _dict(entry.get("attachment"))
    if entry.get("type") != ENTRY_ATTACHMENT:
        return None
    if attachment.get("type") != ATTACHMENT_HOOK_BLOCK:
        return None
    if attachment.get("hookEvent") != HOOK_EVENT_STOP:
        return None
    reason = _dict(attachment.get("blockingError")).get("blockingError")
    return reason if isinstance(reason, str) else None


def last_stop_block_reasons(newest_first: Iterable[str]) -> list[str]:
    """The reasons the stop hooks gave the last time they kept a turn going.

    Several hooks can refuse the same stop; their entries sit together, before the
    agent's next entry. Empty when no stop was ever refused.
    """
    reasons: list[str] = []
    for entry in _entries(newest_first):
        reason = _stop_block_reason(entry)
        if reason is not None:
            reasons.append(reason)
        elif reasons and entry.get("type") == ENTRY_ASSISTANT:
            break  # the agent's turn before that stop: the group is complete
    return reasons
