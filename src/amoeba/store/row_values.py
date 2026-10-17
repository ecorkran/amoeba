"""Typed reads of stored column values, shared by the row mappers.

Each helper raises ``UnknownVocabularyValueError`` naming the column rather than
defaulting, so a malformed stored row never becomes a plausible record.
"""

from __future__ import annotations

from amoeba.store.models import UnknownVocabularyValueError


def text(value: object, column: str) -> str:
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")
    return value


def optional_text(value: object, column: str) -> str | None:
    return None if value is None else text(value, column)


def integer(value: object, column: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise UnknownVocabularyValueError(f"{column} is not an integer: {value!r}")
    return value
