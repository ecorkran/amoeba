"""The server instructions are an agent's first read: they must cover every tool."""

from __future__ import annotations

import pytest
from request_marker_text import assert_marker_rule

from amoeba.mcp.server import INSTRUCTIONS
from amoeba.mcp.tools import TOOLS


@pytest.mark.parametrize("tool", [spec.name.value for spec in TOOLS])
def test_instructions_name_every_tool(tool: str) -> None:
    assert f"`{tool}`" in INSTRUCTIONS


def test_instructions_say_what_amoeba_is() -> None:
    assert "Squadron" in INSTRUCTIONS
    assert "pauses on a question" in INSTRUCTIONS


def test_instructions_give_the_request_marker_line_with_a_placeholder_id() -> None:
    assert_marker_rule(INSTRUCTIONS)


def test_instructions_say_a_note_needs_no_reply_and_arrives_under_notes() -> None:
    assert "`kind` `note`" in INSTRUCTIONS
    assert "`to_program`" in INSTRUCTIONS
    assert "needs no reply" in INSTRUCTIONS
    assert "`notes`" in INSTRUCTIONS


def test_instructions_name_every_release_note_outcome() -> None:
    assert "recorded, versioned, corrected or withdrew" in INSTRUCTIONS
