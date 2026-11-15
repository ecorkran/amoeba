"""Field rules shared by the release report and a request's ``done`` result.

A full commit hash and a version tag mean the same wherever an agent gives one, so the
rules live here once (slice 227 wrote them for ``report_release``; slice 240 reuses
them for ``reply``).
"""

from __future__ import annotations

import re
from typing import Annotated, Final

from pydantic import StrictStr, StringConstraints

#: A full git object name: SHA-1 or SHA-256, in hex.
FULL_HASH_LENGTHS: Final = (40, 64)
_HEX: Final = re.compile(r"[0-9a-f]+")

#: The longest version tag accepted. Over it is ``malformed``, naming the limit.
MAX_VERSION_LENGTH: Final = 128


def bounded_text(max_length: int) -> StringConstraints:
    """A stripped, non-empty string of at most ``max_length`` characters."""
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)


Version = Annotated[StrictStr, bounded_text(MAX_VERSION_LENGTH)]


def full_commit_hash(value: str) -> str:
    """``value`` as a lower-case full commit hash.

    Raises:
        ValueError: It is not 40 or 64 hex characters (an abbreviation, say).
    """
    commit = value.strip().lower()
    if len(commit) not in FULL_HASH_LENGTHS or not _HEX.fullmatch(commit):
        raise ValueError(
            "must be a full commit hash of "
            f"{' or '.join(str(length) for length in FULL_HASH_LENGTHS)} hex "
            "characters, not an abbreviation; `git rev-parse` gives a full hash"
        )
    return commit


def tag_name(value: str | None) -> str | None:
    """``value`` unchanged when it is a tag name (or ``None``).

    Raises:
        ValueError: It holds whitespace or a control character.
    """
    if value is not None and any(
        character.isspace() or not character.isprintable() for character in value
    ):
        raise ValueError("must be a tag name: no whitespace and no control characters")
    return value
