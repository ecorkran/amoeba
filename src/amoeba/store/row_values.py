"""Typed reads of stored column values.

Each helper raises ``StoreRowError`` naming the column rather than defaulting, so
a malformed stored row never becomes a plausible record.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum

from amoeba.store.errors import StoreRowError


def text(value: object, column: str) -> str:
    if not isinstance(value, str):
        raise StoreRowError(f"{column} is not a string: {value!r}")
    return value


def optional_text(value: object, column: str) -> str | None:
    return None if value is None else text(value, column)


def integer(value: object, column: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StoreRowError(f"{column} is not an integer: {value!r}")
    return value


def vocabulary[EnumT: StrEnum](value: object, enum: type[EnumT], column: str) -> EnumT:
    """The member of ``enum`` the column holds."""
    try:
        return enum(text(value, column))
    except ValueError as error:
        # Specific: a stored string outside the closed vocabulary is corruption.
        raise StoreRowError(
            f"{column} value {value!r} is not a valid {enum.__name__}"
        ) from error


def _decode_json(value: object, column: str) -> object:
    try:
        return json.loads(text(value, column))
    except json.JSONDecodeError as error:
        # Specific: a stored column that is not valid JSON is corruption.
        raise StoreRowError(f"{column} is not valid JSON: {value!r}") from error


def _narrow_mapping(decoded: object, column: str) -> Mapping[str, object]:
    if not isinstance(decoded, dict):
        raise StoreRowError(f"{column} is not a JSON object: {decoded!r}")
    narrowed: dict[str, object] = {}
    for key, item in decoded.items():  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(key, str):
            raise StoreRowError(f"{column} has a non-string key: {key!r}")
        narrowed[key] = item
    return narrowed


def decode_mapping(value: object, column: str) -> Mapping[str, object]:
    """A stored JSON object column, or ``StoreRowError``."""
    return _narrow_mapping(_decode_json(value, column), column)


def decode_mapping_list(value: object, column: str) -> tuple[Mapping[str, object], ...]:
    """A stored JSON array of objects, or ``StoreRowError``."""
    decoded = _decode_json(value, column)
    if not isinstance(decoded, list):
        raise StoreRowError(f"{column} is not a JSON array: {value!r}")
    items: list[object] = list(decoded)  # pyright: ignore[reportUnknownArgumentType]
    return tuple(_narrow_mapping(item, column) for item in items)


def decode_string_list(value: object, column: str) -> tuple[str, ...]:
    """A stored JSON array of strings, as a tuple, or ``StoreRowError``."""
    decoded = _decode_json(value, column)
    if not isinstance(decoded, list):
        raise StoreRowError(f"{column} is not a JSON array: {value!r}")
    items: list[str] = []
    for item in decoded:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item, str):
            raise StoreRowError(f"{column} holds a non-string item: {item!r}")
        items.append(item)
    return tuple(items)


def encode_string_list(items: tuple[str, ...]) -> str:
    """The JSON array text stored for a string-list column."""
    return json.dumps(list(items))


def decode_timestamp(value: object, column: str) -> datetime:
    """A stored UTC ISO-8601 time, as an aware datetime."""
    try:
        moment = datetime.fromisoformat(text(value, column))
    except ValueError as error:
        # Specific: a stored timestamp that is not ISO-8601 is corruption.
        raise StoreRowError(
            f"{column} is not an ISO-8601 timestamp: {value!r}"
        ) from error
    if moment.tzinfo is None:
        raise StoreRowError(f"{column} has no timezone: {value!r}")
    return moment.astimezone(UTC)


def encode_timestamp(moment: datetime) -> str:
    """The text stored for a time: UTC ISO-8601. A naive time is a bug."""
    if moment.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {moment!r}")
    return moment.astimezone(UTC).isoformat()
