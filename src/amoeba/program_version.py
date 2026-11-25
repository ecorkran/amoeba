"""The version of the installed package, read once (slice 263, D6).

A session row names the version of the program serving it. The client sends the same
value with every call, so both read it here.
"""

from __future__ import annotations

from functools import cache
from importlib import metadata
from typing import Final

PACKAGE_NAME: Final = "amoeba-ai"


@cache
def program_version() -> str:
    """The installed package version."""
    return metadata.version(PACKAGE_NAME)
