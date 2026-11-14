"""The one rule for a caller-supplied starting time (slices 224 and 227).

``decisions`` and ``changes`` both take ``since`` as ISO-8601 with a UTC offset and
compare it against the store's UTC text, so the parsing lives here once.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.store.row_values import encode_timestamp


def parse_since(value: str) -> str:
    """The store's UTC text for an ISO-8601 time that carries an offset.

    Raises:
        ValueError: The value does not parse, or has no UTC offset.
    """
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError as error:
        raise ValueError(f"not an ISO-8601 time: {value!r}") from error
    if moment.tzinfo is None:
        raise ValueError(f"has no UTC offset: {value!r}")
    return encode_timestamp(moment)
