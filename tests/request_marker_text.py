"""What the rules text says about the request marker line (slice 242, task 9.1).

Shared by the program-rules and MCP-instructions tests: both carry the same rule, with
a placeholder for the id and never a sample one.
"""

from __future__ import annotations

import re
from typing import Final

from amoeba.operations.request_link import MARKER_WORDS

#: The marker as the rules write it, with the placeholder the agent fills in.
MARKER_RULE: Final = f"`{MARKER_WORDS[0]}-{MARKER_WORDS[1]}: <id>`"
#: Whatever follows each marker the text writes.
_AFTER_MARKER: Final = re.compile(
    rf"{MARKER_WORDS[0]}-{MARKER_WORDS[1]}:\s*(\S*)", re.IGNORECASE
)
PLACEHOLDER_START: Final = "<"


def ids_after_markers(text: str) -> list[str]:
    """What each marker in ``text`` is followed by."""
    return _AFTER_MARKER.findall(text)


def assert_marker_rule(text: str) -> None:
    """``text`` gives the marker rule with a placeholder and no sample id."""
    assert MARKER_RULE in text
    assert "nothing else on that line" in text
    following = ids_after_markers(text)
    assert following, "the text writes the marker"
    for found in following:
        assert found.startswith(PLACEHOLDER_START), f"a sample id: {found!r}"
