"""Read the two pasted rule blocks out of ``docs/program-rules.md`` (slice 227, D6).

Parsed leniently: a block is the first fenced code block under the heading whose title
names it, at any heading depth, with any fence length or marker and any whitespace.
The flow test and the rule-blocks test both read the real file through this.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

PROGRAM_RULES: Final = Path(__file__).parent.parent / "docs" / "program-rules.md"

_HEADING: Final = re.compile(r"^[ \t]*#{1,6}[ \t]+(?P<title>.+?)[ \t]*#*[ \t]*$")
_FENCE_OPEN: Final = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})[^`\n]*$")


@dataclass(frozen=True)
class RuleBlocks:
    """The text each repo pastes: a consumer's and a provider's."""

    consumer: str
    provider: str


def _section_lines(lines: list[str], keyword: str) -> list[str]:
    """The lines under the first heading whose title contains ``keyword``, up to the
    next heading. A ``#`` line inside a fence is text, not a heading."""
    section: list[str] = []
    inside = False
    fence: str | None = None
    for line in lines:
        if fence is not None:
            if line.strip().startswith(fence):
                fence = None
            if inside:
                section.append(line)
            continue
        opened = _FENCE_OPEN.match(line)
        if opened is not None:
            fence = opened["fence"]
            if inside:
                section.append(line)
            continue
        heading = _HEADING.match(line)
        if heading is None:
            if inside:
                section.append(line)
            continue
        if inside:
            break
        inside = keyword in heading["title"].lower()
    return section


def _fenced_text(section: list[str], keyword: str) -> str:
    body: list[str] = []
    fence: str | None = None
    for line in section:
        opened = _FENCE_OPEN.match(line)
        if fence is None:
            if opened is not None:
                fence = opened["fence"]
            continue
        if line.strip().startswith(fence):
            return "\n".join(body).strip()
        body.append(line)
    raise ValueError(f"no complete fenced block under the {keyword!r} heading")


def rule_blocks(text: str) -> RuleBlocks:
    """The consumer and provider blocks of ``text``.

    Raises:
        ValueError: A block's heading or its fenced text is missing.
    """
    lines = text.splitlines()
    found: dict[str, str] = {}
    for keyword in ("consumer", "provider"):
        section = _section_lines(lines, keyword)
        if not section:
            raise ValueError(f"no heading names the {keyword!r} block")
        found[keyword] = _fenced_text(section, keyword)
    return RuleBlocks(consumer=found["consumer"], provider=found["provider"])


def real_rule_blocks() -> RuleBlocks:
    """The blocks of the real ``docs/program-rules.md``."""
    return rule_blocks(PROGRAM_RULES.read_text(encoding="utf-8"))
