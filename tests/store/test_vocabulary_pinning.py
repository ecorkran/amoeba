"""Each ``CHECK`` list in the schema equals its enum's values.

A column whose list a later migration rebuilt (``questions.state`` in ``003``) is
checked against its newest definition.
"""

from __future__ import annotations

import re
from enum import StrEnum
from importlib import resources
from importlib.resources.abc import Traversable

import pytest

from amoeba.answering.values import AnsweredBy
from amoeba.store.vocabulary import (
    ClosedReason,
    ConsumedMode,
    Door,
    QuestionState,
    ResumeOutcome,
)

SCHEMA_FILES = sorted(
    (resources.files("amoeba.store") / "schema").iterdir(), key=lambda f: f.name
)
#: ``CHECK (col IN ('a', 'b'))``, with an optional ``col IS NULL OR`` before it.
CHECK_LIST = re.compile(
    r"CHECK\s*\(\s*(?:\w+\s+IS\s+NULL\s+OR\s+)?(\w+)\s+IN\s*\(([^)]*)\)", re.IGNORECASE
)
ENUM_FOR_COLUMN: dict[str, type[StrEnum]] = {
    "consumed": ConsumedMode,
    "state": QuestionState,
    "answered_by": AnsweredBy,
    "resume_outcome": ResumeOutcome,
    "closed_reason": ClosedReason,
    "via": Door,
}


def _check_lists(files: list[Traversable]) -> dict[str, set[str]]:
    """Each column's newest ``CHECK`` list: a later file's definition replaces."""
    lists: dict[str, set[str]] = {}
    for file in files:
        for column, body in CHECK_LIST.findall(file.read_text(encoding="utf-8")):
            lists[column] = set(re.findall(r"'([^']*)'", body))
    return lists


def test_every_check_list_is_found() -> None:
    assert set(_check_lists(SCHEMA_FILES)) == set(ENUM_FOR_COLUMN)


@pytest.mark.parametrize("column", sorted(ENUM_FOR_COLUMN))
def test_check_list_equals_enum_values(column: str) -> None:
    listed = _check_lists(SCHEMA_FILES)[column]

    assert listed == {member.value for member in ENUM_FOR_COLUMN[column]}
