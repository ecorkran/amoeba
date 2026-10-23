"""Checks and encodings shared by the store's validated writes.

Every failure is the ``ValueError`` a malformed write raises, before any
transaction opens.
"""

from __future__ import annotations

import json
from collections.abc import Mapping


def require_text(value: str, name: str) -> None:
    """Raise ``ValueError`` unless ``value`` holds non-blank text."""
    if not value.strip():
        raise ValueError(f"{name} must be non-empty text")


def encode_object(value: Mapping[str, object], name: str) -> str:
    """JSON-encode a mapping, or raise ``ValueError`` if it cannot be."""
    try:
        return json.dumps(dict(value))
    except TypeError as error:
        # Specific: a value that is not JSON-serializable is a caller error,
        # reported as the ValueError every malformed write raises.
        raise ValueError(f"{name} is not JSON-serializable: {error}") from error
