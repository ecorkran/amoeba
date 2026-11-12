"""``set_up`` ``remove``: the request shape and its three contradictions (228 D8)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from amoeba.operations.set_up_models import (
    RemoveRequest,
    SetUpOutcome,
    SetUpProblemCode,
    SetUpRequest,
    SetUpResult,
)
from amoeba.store.store import Store
from operations.set_up_support import row_counts, run_set_up

PROJECTS = [("provider-id", "provider"), ("consumer-id", "consumer")]
RULES = {"rules_paths": ["CLAUDE.md"]}
EMPTY = {"programs": 0, "members": 0, "dependency_pairs": 0}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _malformed(store: Store, document: dict[str, Any]) -> SetUpResult:
    result = run_set_up(store, document, projects=PROJECTS)
    assert result.outcome is SetUpOutcome.REJECTED
    assert result.changes == ()
    assert row_counts(store) == EMPTY
    return result


def _details(result: SetUpResult) -> list[str]:
    assert {problem.code for problem in result.problems} == {SetUpProblemCode.MALFORMED}
    return [problem.detail for problem in result.problems]


def test_a_request_without_remove_removes_nothing() -> None:
    request = SetUpRequest.model_validate({"program": "demo"})

    assert request.remove == RemoveRequest()
    assert request.remove.members == ()
    assert request.remove.pairs == ()


def test_a_request_without_remove_still_applies_as_before(store: Store) -> None:
    document = {
        "program": "demo",
        "members": [{"project": "provider", **RULES}],
    }

    first = run_set_up(store, document, projects=PROJECTS)
    second = run_set_up(store, document, projects=PROJECTS)

    assert first.outcome is SetUpOutcome.APPLIED
    assert second.outcome is SetUpOutcome.UNCHANGED


def test_remove_accepts_member_references_and_pairs() -> None:
    request = SetUpRequest.model_validate(
        {
            "program": "demo",
            "remove": {
                "members": ["provider"],
                "pairs": [{"provider": "provider", "consumer": "consumer"}],
            },
        }
    )

    assert request.remove.members == ("provider",)
    assert request.remove.pairs[0].consumer == "consumer"


@pytest.mark.parametrize(
    ("remove", "named"),
    [
        ({"surprise": 1}, "remove.surprise"),
        ({"members": [""]}, "remove.members.0"),
        ({"pairs": [{"provider": "provider"}]}, "remove.pairs.0.consumer"),
    ],
)
def test_a_bad_remove_is_malformed_naming_the_field(
    store: Store, remove: dict[str, Any], named: str
) -> None:
    result = _malformed(
        store,
        {
            "program": "demo",
            "members": [{"project": "provider", **RULES}],
            "remove": remove,
        },
    )

    assert any(named in detail for detail in _details(result))


def test_a_member_under_both_members_and_remove_members_is_malformed(
    store: Store,
) -> None:
    result = _malformed(
        store,
        {
            "program": "demo",
            "members": [
                {"project": "consumer", **RULES},
                {"project": "provider", **RULES},
            ],
            "remove": {"members": ["provider"]},
        },
    )

    (detail,) = _details(result)
    assert "remove.members.0" in detail
    assert "members.1" in detail


def test_the_same_member_by_name_and_by_id_is_still_caught(store: Store) -> None:
    result = _malformed(
        store,
        {
            "program": "demo",
            "members": [{"project": "provider-id", **RULES}],
            "remove": {"members": ["provider"]},
        },
    )

    (detail,) = _details(result)
    assert "remove.members.0" in detail


def test_a_pair_under_both_depends_on_and_remove_pairs_is_malformed(
    store: Store,
) -> None:
    result = _malformed(
        store,
        {
            "program": "demo",
            "members": [
                {"project": "provider", **RULES},
                {
                    "project": "consumer",
                    **RULES,
                    "depends_on": [{"provider": "provider", "consumed": "from_source"}],
                },
            ],
            "remove": {"pairs": [{"provider": "provider", "consumer": "consumer"}]},
        },
    )

    (detail,) = _details(result)
    assert "remove.pairs.0" in detail
    assert "members.1.depends_on.0" in detail


def test_removing_a_member_named_as_a_pair_end_is_malformed(store: Store) -> None:
    result = _malformed(
        store,
        {
            "program": "demo",
            "members": [{"project": "consumer", **RULES}],
            "remove": {
                "members": ["provider"],
                "pairs": [{"provider": "provider", "consumer": "consumer"}],
            },
        },
    )

    (detail,) = _details(result)
    assert "remove.pairs.0.provider" in detail
    assert "remove.members.0" in detail


def test_removing_a_member_another_member_depends_on_is_malformed(
    store: Store,
) -> None:
    result = _malformed(
        store,
        {
            "program": "demo",
            "members": [
                {
                    "project": "consumer",
                    **RULES,
                    "depends_on": [{"provider": "provider", "consumed": "from_source"}],
                }
            ],
            "remove": {"members": ["provider"]},
        },
    )

    (detail,) = _details(result)
    assert "members.0.depends_on.0.provider" in detail
    assert "remove.members.0" in detail
