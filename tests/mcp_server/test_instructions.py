"""The server instructions are an agent's first read: they must cover every tool."""

from __future__ import annotations

import pytest

from amoeba.mcp.server import INSTRUCTIONS
from amoeba.mcp.tools import TOOLS


@pytest.mark.parametrize("tool", [spec.name.value for spec in TOOLS])
def test_instructions_name_every_tool(tool: str) -> None:
    assert f"`{tool}`" in INSTRUCTIONS


def test_instructions_say_what_amoeba_is() -> None:
    assert "Squadron" in INSTRUCTIONS
    assert "pauses on a question" in INSTRUCTIONS
