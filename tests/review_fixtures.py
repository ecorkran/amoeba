"""Read captured Squadron review files for tests.

A test helper, not the slice 108 parser: it reads the YAML frontmatter of the
byte-real review files in ``tests/fixtures/sq_reviews/`` and hands back the
fields tests need. A malformed file fails loudly with its name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

SQ_REVIEWS = Path(__file__).parent / "fixtures" / "sq_reviews"

_REVIEW_STEM = "102-review.tasks.resident-process-and-recovery"
ROUND_1_PART_1 = SQ_REVIEWS / f"{_REVIEW_STEM}.part-1.20260921T112529.md"
ROUND_1_PART_2 = SQ_REVIEWS / f"{_REVIEW_STEM}.part-2.20260921T112635.md"
ROUND_2_PART_1 = SQ_REVIEWS / f"{_REVIEW_STEM}.part-1.md"
ROUND_2_PART_2 = SQ_REVIEWS / f"{_REVIEW_STEM}.part-2.md"

# Frontmatter is the block between the first two lines consisting of `---`.
_FRONTMATTER_FENCE = re.compile(r"^---[ \t]*$", re.MULTILINE)

# Squadron writes a failed provider call as a normal review slot with this heading.
_PROVIDER_FAILURE_HEADING = re.compile(
    r"^#{1,6}\s*provider failure\s*$", re.MULTILINE | re.IGNORECASE
)


def has_provider_failure_heading(path: Path) -> bool:
    return (
        _PROVIDER_FAILURE_HEADING.search(path.read_text(encoding="utf-8")) is not None
    )


@dataclass(frozen=True)
class CapturedFinding:
    position_id: str
    severity: str
    category: str | None
    summary: str
    location: str | None


def read_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fences = list(_FRONTMATTER_FENCE.finditer(text))
    if len(fences) < 2 or fences[0].start() != 0:
        raise ValueError(f"{path.name}: no YAML frontmatter block")
    loaded: object = yaml.safe_load(text[fences[0].end() : fences[1].start()])
    if not isinstance(loaded, dict):
        raise ValueError(f"{path.name}: frontmatter is not a mapping")
    return cast(dict[str, Any], loaded)


def _optional_text(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    return None if value is None else str(value)


def review_findings(path: Path) -> list[CapturedFinding]:
    """The findings list from a review file's frontmatter; empty when absent."""
    raw_findings: object = read_frontmatter(path).get("findings") or []
    if not isinstance(raw_findings, list):
        raise ValueError(f"{path.name}: findings is not a list")
    findings: list[CapturedFinding] = []
    for entry in cast(list[object], raw_findings):
        if not isinstance(entry, dict):
            raise ValueError(f"{path.name}: a finding is not a mapping")
        raw = cast(dict[str, Any], entry)
        findings.append(
            CapturedFinding(
                position_id=str(raw["id"]),
                severity=str(raw["severity"]),
                category=_optional_text(raw, "category"),
                summary=str(raw["summary"]),
                location=_optional_text(raw, "location"),
            )
        )
    return findings
