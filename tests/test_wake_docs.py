"""The wake-command docs: the example carries a cap (slice 244, D12).

The contract requires every wake command to carry its own cost or time cap, because
it is the only bound on a command whose wrapper is killed. The example in
``cli-contract.md`` is what a person copies, so it must carry one.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from amoeba.operations.wake_environment import WAKE_ENV_NAMES

CLI_CONTRACT: Final = Path(__file__).parents[1] / "docs" / "cli-contract.md"
SECTION_HEADING: Final = "## The wake command"
CAP_FLAG: Final = "--max-seconds"
EXAMPLE_PREFIX: Final = "amoeba add --wake-command"
FENCE: Final = "```"


def _section(text: str) -> str:
    """The text of ``## The wake command``, up to the next ``## `` heading."""
    start = text.index(SECTION_HEADING) + len(SECTION_HEADING)
    following = re.search(r"^## ", text[start:], re.MULTILINE)
    end = len(text) if following is None else start + following.start()
    return text[start - len(SECTION_HEADING) : end]


def _example(section: str) -> str:
    """The example ``add --wake-command`` line of the section."""
    lines = [line for line in section.splitlines() if line.startswith(EXAMPLE_PREFIX)]
    assert len(lines) == 1, f"the section has {len(lines)} example lines, not one"
    return lines[0]


def _has_a_cap(example: str) -> bool:
    return CAP_FLAG in example


def test_the_example_carries_a_cap() -> None:
    text = CLI_CONTRACT.read_text(encoding="utf-8")

    assert _has_a_cap(_example(_section(text)))


def test_the_check_fails_when_the_flag_is_removed_from_a_copy() -> None:
    text = CLI_CONTRACT.read_text(encoding="utf-8")
    example = _example(_section(text))

    without = re.sub(rf"\s*{re.escape(CAP_FLAG)}\s+\S+", "", example)

    assert without != example
    assert not _has_a_cap(without)
    with pytest.raises(AssertionError):
        assert _has_a_cap(_example(_section(text.replace(example, without))))


def test_the_section_states_the_duties_the_contract_requires() -> None:
    section = _section(CLI_CONTRACT.read_text(encoding="utf-8"))

    for phrase in (
        "must carry its own cost or time cap",
        "no stdin",
        "wake_timeout_seconds",
        "plain text",
        "log files",
        "`inbox`",
        "WAKE_ENV_NAMES",
        "overdue",
    ):
        assert phrase in section, f"the wake command section lacks {phrase!r}"
    for name in WAKE_ENV_NAMES:
        assert f"`{name}`" in section
