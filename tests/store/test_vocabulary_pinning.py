"""Each ``CHECK`` list in the baseline schema equals its enum's values."""

from __future__ import annotations

import re
from enum import StrEnum
from importlib import resources

import pytest

from amoeba.answering.values import AnsweredBy
from amoeba.store.vocabulary import ConsumedMode, QuestionState, ResumeOutcome

SCHEMA_TEXT = (
    resources.files("amoeba.store") / "schema" / "001_baseline.sql"
).read_text(encoding="utf-8")
#: ``CHECK (col IN ('a', 'b'))``, with an optional ``col IS NULL OR`` before it.
CHECK_LIST = re.compile(
    r"CHECK\s*\(\s*(?:\w+\s+IS\s+NULL\s+OR\s+)?(\w+)\s+IN\s*\(([^)]*)\)", re.IGNORECASE
)
ENUM_FOR_COLUMN: dict[str, type[StrEnum]] = {
    "consumed": ConsumedMode,
    "state": QuestionState,
    "answered_by": AnsweredBy,
    "resume_outcome": ResumeOutcome,
}


def _check_lists(text: str) -> dict[str, set[str]]:
    return {
        column: set(re.findall(r"'([^']*)'", body))
        for column, body in CHECK_LIST.findall(text)
    }


def test_every_check_list_is_found() -> None:
    assert set(_check_lists(SCHEMA_TEXT)) == set(ENUM_FOR_COLUMN)


@pytest.mark.parametrize("column", sorted(ENUM_FOR_COLUMN))
def test_check_list_equals_enum_values(column: str) -> None:
    listed = _check_lists(SCHEMA_TEXT)[column]

    assert listed == {member.value for member in ENUM_FOR_COLUMN[column]}
