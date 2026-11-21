"""Answer first: what counts as a PM message, as a reply, and as a kept-going stop.

The entries come from ``tests/transcript_entries.py``, which carries the fields Claude
Code wrote in a real session transcript on 2026-11-21.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from transcript_entries import (
    HOOK_FEEDBACK,
    INTERRUPTED,
    PEER_MESSAGE,
    SLASH_COMMAND,
    TASK_NOTIFICATION,
    TEXT,
    THINKING,
    TOOL_RESULT,
    TOOL_USE,
    agent,
    newest_first,
    pm_mid_turn,
    pm_prompt,
    stop_block,
)

from amoeba.operations.answer_first import (
    PmMessage,
    is_agent_text,
    is_pm_message,
    last_stop_block_reasons,
    latest_pm_message,
)


def latest(*entries: dict[str, Any]) -> PmMessage | None:
    return latest_pm_message(newest_first(*entries))


@pytest.mark.parametrize(
    "entry", [pm_prompt("where are we?", "p1"), pm_mid_turn("wait", "p2")]
)
def test_what_the_pm_typed_is_a_pm_message(entry: dict[str, Any]) -> None:
    assert is_pm_message(entry)


@pytest.mark.parametrize(
    "entry",
    [
        TOOL_RESULT,
        HOOK_FEEDBACK,
        PEER_MESSAGE,
        TASK_NOTIFICATION,
        SLASH_COMMAND,
        INTERRUPTED,
        {"type": "attachment", "attachment": {"type": "output_style"}},
        stop_block("Amoeba answer-first: carry on"),
        TEXT,
    ],
)
def test_everything_else_is_not_a_pm_message(entry: dict[str, Any]) -> None:
    assert not is_pm_message(entry)


def test_only_non_blank_text_is_a_reply() -> None:
    assert is_agent_text(TEXT)
    assert not is_agent_text(THINKING)
    assert not is_agent_text(TOOL_USE)
    assert not is_agent_text(agent({"type": "text", "text": "  \n"}))


def test_a_pm_message_with_nothing_written_since_is_not_replied_to() -> None:
    assert latest(TEXT, pm_prompt("what is breaking?", "p1"), THINKING) == PmMessage(
        "p1", replied=False
    )


def test_text_after_the_pm_message_is_a_reply() -> None:
    entries = (pm_prompt("what is breaking?", "p1"), THINKING, TEXT, TOOL_USE)
    assert latest(*entries) == PmMessage("p1", replied=True)


def test_a_message_sent_mid_turn_is_the_latest_and_needs_its_own_reply() -> None:
    before = (pm_prompt("go", "p1"), TEXT, TOOL_USE, TOOL_RESULT)
    assert latest(*before, pm_mid_turn("wait, what?", "p2"), THINKING) == PmMessage(
        "p2", replied=False
    )
    assert latest(*before, pm_mid_turn("wait, what?", "p2"), TEXT) == PmMessage(
        "p2", replied=True
    )


def test_feedback_notifications_peers_and_slash_commands_are_passed_over() -> None:
    turn = (pm_prompt("go", "p1"), TEXT)
    for later in (
        HOOK_FEEDBACK,
        PEER_MESSAGE,
        TASK_NOTIFICATION,
        INTERRUPTED,
        SLASH_COMMAND,
    ):
        assert latest(*turn, later, THINKING) == PmMessage("p1", replied=True)


def test_a_subagents_conversation_is_not_read() -> None:
    sidechain_prompt = {**pm_prompt("a subagent's task", "s1"), "isSidechain": True}
    sidechain_text = {**TEXT, "isSidechain": True}

    assert latest(sidechain_prompt, THINKING) is None
    assert latest(pm_prompt("go", "p1"), sidechain_text) == PmMessage("p1", False)


def test_a_transcript_with_no_pm_message_has_none() -> None:
    assert latest(SLASH_COMMAND, TASK_NOTIFICATION, THINKING, TOOL_USE) is None
    assert latest_pm_message([]) is None


def test_a_pm_message_with_no_id_cannot_be_released_and_counts_as_none() -> None:
    no_id = pm_prompt("hi", "p1")
    del no_id["uuid"]

    assert latest(no_id, THINKING) is None


def test_unreadable_lines_and_other_shapes_are_passed_over() -> None:
    lines = ['{"type": "assis', "[1, 2]", '"text"', json.dumps(pm_prompt("hi", "p1"))]

    assert latest_pm_message(lines) == PmMessage("p1", replied=False)


def test_the_last_stop_blocks_reasons_are_those_before_the_agents_next_entry() -> None:
    entries = (
        pm_prompt("go", "p1"),
        TEXT,
        HOOK_FEEDBACK,
        stop_block("first stop"),
        THINKING,
        TOOL_USE,
        TOOL_RESULT,
        TEXT,
        HOOK_FEEDBACK,
        stop_block("second stop, one hook"),
        stop_block("second stop, another hook"),
        THINKING,
        TOOL_USE,
    )

    assert last_stop_block_reasons(newest_first(*entries)) == [
        "second stop, another hook",
        "second stop, one hook",
    ]


def test_a_turn_never_kept_going_has_no_stop_block_reasons() -> None:
    tool_refusal = stop_block("a tool was refused")
    tool_refusal["attachment"]["hookEvent"] = "PreToolUse"

    assert last_stop_block_reasons(newest_first(pm_prompt("go", "p1"), TEXT)) == []
    assert last_stop_block_reasons(newest_first(TEXT, tool_refusal, THINKING)) == []
