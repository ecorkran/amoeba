"""The finding matching rule: content keys that survive formatting-only changes.

Pure functions over text, importable without opening a store. The rule removes
formatting (whitespace, backticks, letter case, trailing punctuation, line
numbers) and nothing else. It deliberately does not match a reworded finding;
deciding two wordings are the same issue is judgment, owned by initiative 140.

Every stored observation records ``RULE_VERSION``. Keys are only ever compared
within one version, and raw text is kept so a later version can be recomputed.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Final

RULE_VERSION: Final = 1

# Squadron writes this literal when a finding has no location.
UNVERIFIED_LOCATION: Final = "unverified"

_TRAILING_SUMMARY_PUNCTUATION: Final = ".;:"

_WHITESPACE_RUN = re.compile(r"\s+")

# Line references anywhere in a location. Covers `:12`, `:12-30`, `:12:4`,
# comma lists Squadron emits (`:34-37,55-58`), `#L12`, `#L12-L30`, and
# `, line 12` / `, lines 12-30`. Heading anchors such as `#data-flow` are kept.
_LINE_REFERENCE = re.compile(
    r"#L\d+(?:[-–]L?\d+)?"
    r"|:\d+(?:[-–:]\d+)*(?:,\s*\d+(?:[-–]\d+)*)*"
    r"|,\s*lines?\s+\d+(?:\s*[-–]\s*\d+)?",
    re.IGNORECASE,
)


def _collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RUN.sub(" ", text).strip()


def normalize_summary(summary: str) -> str:
    """Apply the five summary steps of rule version 1, in order."""
    text = unicodedata.normalize("NFKC", summary)
    text = text.replace("`", "")
    text = text.casefold()
    text = _collapse_whitespace(text)
    return text.rstrip(_TRAILING_SUMMARY_PUNCTUATION).rstrip()


def normalize_location(location: str | None) -> str:
    """Apply the four location steps of rule version 1, in order. Case is kept."""
    if location is None:
        return ""
    stripped = location.strip()
    if not stripped or stripped.casefold() == UNVERIFIED_LOCATION:
        return ""
    text = unicodedata.normalize("NFKC", stripped)
    text = text.replace("\\", "/")
    text = text.removeprefix("./")
    text = _LINE_REFERENCE.sub("", text)
    return _collapse_whitespace(text)


def finding_identity(location: str | None, summary: str) -> str:
    """Return the hex SHA-256 content key for one finding under this rule version."""
    fields = (
        f"v{RULE_VERSION}",
        normalize_location(location),
        normalize_summary(summary),
    )
    # Length-prefixed so no character inside a field can shift text between fields.
    material = "".join(f"{len(field)}:{field}" for field in fields)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
