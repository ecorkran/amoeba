"""Each ``CHECK`` list in the schema equals its enum's values.

Lists are keyed by ``table.column`` (``questions.state`` and ``messages.state`` are
different columns). A column whose list a later migration rebuilt (``questions.state``
in ``003``) is checked against its newest definition.
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
    DeliveryEvent,
    Door,
    MessageKind,
    QuestionState,
    RequestState,
    ResumeOutcome,
    RulesFrom,
    StandingReach,
    WakeOutcome,
)

SCHEMA_FILES = sorted(
    (resources.files("amoeba.store") / "schema").iterdir(), key=lambda f: f.name
)
#: ``CHECK (col IN ('a', 'b'))``, with an optional ``col IS NULL OR`` before it.
CHECK_LIST = re.compile(
    r"CHECK\s*\(\s*(?:\w+\s+IS\s+NULL\s+OR\s+)?(\w+)\s+IN\s*\(([^)]*)\)", re.IGNORECASE
)
#: ``ALTER TABLE old RENAME TO new``: the lists of ``old`` now belong to ``new``.
RENAME_STATEMENT = re.compile(
    r"ALTER\s+TABLE\s+(\w+)\s+RENAME\s+TO\s+(\w+)", re.IGNORECASE
)
#: The table a statement creates or alters; the ``CHECK`` lists after it are its.
TABLE_STATEMENT = re.compile(
    r"^\s*(?:CREATE\s+TABLE|ALTER\s+TABLE)\s+(\w+)", re.IGNORECASE | re.MULTILINE
)
ENUM_FOR_COLUMN: dict[str, type[StrEnum]] = {
    "dependency_pairs.consumed": ConsumedMode,
    "questions.state": QuestionState,
    "answers.answered_by": AnsweredBy,
    "answers.resume_outcome": ResumeOutcome,
    "questions.closed_reason": ClosedReason,
    "answers.via": Door,
    "members.rules_from": RulesFrom,
    "messages.kind": MessageKind,
    "messages.state": RequestState,
    "deliveries.event": DeliveryEvent,
    "wakes.outcome": WakeOutcome,
    "standing_answers.reach": StandingReach,
}


def _check_lists(files: list[Traversable]) -> dict[str, set[str]]:
    """Each column's newest ``CHECK`` list: a later file's definition replaces."""
    lists: dict[str, set[str]] = {}
    for file in files:
        for statement in re.split(
            r";\s*$", file.read_text(encoding="utf-8"), flags=re.M
        ):
            renamed = RENAME_STATEMENT.search(statement)
            if renamed is not None:
                old, new = renamed.groups()
                lists = {
                    (f"{new}{key[len(old) :]}" if key.startswith(f"{old}.") else key): v
                    for key, v in lists.items()
                }
                continue
            table = TABLE_STATEMENT.search(statement)
            for column, body in CHECK_LIST.findall(statement):
                assert table is not None, f"a CHECK list outside a table: {column}"
                lists[f"{table.group(1)}.{column}"] = set(
                    re.findall(r"'([^']*)'", body)
                )
    return lists


def test_every_check_list_is_found() -> None:
    assert set(_check_lists(SCHEMA_FILES)) == set(ENUM_FOR_COLUMN)


@pytest.mark.parametrize("column", sorted(ENUM_FOR_COLUMN))
def test_check_list_equals_enum_values(column: str) -> None:
    listed = _check_lists(SCHEMA_FILES)[column]

    assert listed == {member.value for member in ENUM_FOR_COLUMN[column]}


def test_questions_state_lists_waiting_on_request_from_migration_008() -> None:
    """The held state (242 D2) is in the newest list, and only from ``008`` on."""
    newest = _check_lists(SCHEMA_FILES)["questions.state"]
    before_008 = _check_lists([file for file in SCHEMA_FILES if file.name < "008"])[
        "questions.state"
    ]

    assert QuestionState.WAITING_ON_REQUEST.value in newest
    assert QuestionState.WAITING_ON_REQUEST.value not in before_008
