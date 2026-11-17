"""Reading fields from a request document that may not validate (slice 240, D9).

A rejection is recorded under the caller, and the caller is resolved from the
document's ``member`` before the document is validated. A malformed document is
still recorded with the id, recipient and parent it gave, so these fields are read
leniently: a field that is missing or not text is ``None``.
"""

from __future__ import annotations

from typing import cast


def declared_text(document: object, field: str) -> str | None:
    """``document[field]`` when ``document`` is an object and the field is text."""
    if not isinstance(document, dict):
        return None
    # A JSON object always has string keys.
    value = cast("dict[str, object]", document).get(field)
    return value if isinstance(value, str) else None


def recipient_ref(to: str | None, to_program: str | None) -> str | None:
    """The one recipient rule: ``to``, else ``to_program``, else ``None``."""
    return to if to is not None else to_program


def declared_recipient(document: object) -> str | None:
    """The recipient as the document gave it: ``to``, else ``to_program`` (243), else
    ``None``. This is what a rejection row keeps as the recipient."""
    return recipient_ref(
        declared_text(document, "to"), declared_text(document, "to_program")
    )
