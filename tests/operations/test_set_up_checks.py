"""``set_up`` checks: one test per code, each leaving the store as it was."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from store.seed import insert_member, insert_program
from user_configs import user_config

from amoeba.operations.set_up import SetUpProblemCode, SetUpResult
from amoeba.operations.set_up_models import SetUpOutcome
from amoeba.store.store import Store
from operations.set_up_support import row_counts, run_set_up

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
PROJECTS = [("provider-id", "provider"), ("consumer-id", "consumer")]
RULES = {"rules_paths": ["CLAUDE.md"]}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _rejected(store: Store, document: dict[str, Any]) -> SetUpResult:
    before = row_counts(store)
    result = run_set_up(store, document, projects=PROJECTS, config=user_config())
    assert result.outcome is SetUpOutcome.REJECTED
    assert result.changes == ()
    assert row_counts(store) == before
    return result


def _codes(result: SetUpResult) -> list[SetUpProblemCode]:
    return [problem.code for problem in result.problems]


def _seed_other_program(store: Store, member_id: str) -> None:
    with store.write() as transaction:
        insert_program(
            transaction,
            program_id="other",
            concept_member=None,
            concept_path=None,
            registered_at=NOW,
            updated_at=NOW,
        )
        insert_member(
            transaction,
            project_id=member_id,
            program_id="other",
            rules_paths=("CLAUDE.md",),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=NOW,
            updated_at=NOW,
        )


def test_empty_program(store: Store) -> None:
    result = _rejected(store, {"program": "demo"})

    assert _codes(result) == [SetUpProblemCode.EMPTY_PROGRAM]
    assert "demo" in result.problems[0].detail
    assert result.program is None


def test_member_of_other_program(store: Store) -> None:
    _seed_other_program(store, "provider-id")

    result = _rejected(
        store, {"program": "demo", "members": [{"project": "provider", **RULES}]}
    )

    assert _codes(result) == [SetUpProblemCode.MEMBER_OF_OTHER_PROGRAM]
    detail = result.problems[0].detail
    assert "members.0" in detail
    assert "provider-id" in detail
    assert "other" in detail


def test_rules_paths_required_for_a_new_member(store: Store) -> None:
    result = _rejected(store, {"program": "demo", "members": [{"project": "provider"}]})

    assert _codes(result) == [SetUpProblemCode.RULES_PATHS_REQUIRED]
    assert "members.0" in result.problems[0].detail


def test_an_empty_rules_paths_list_counts_as_given(store: Store) -> None:
    document: dict[str, Any] = {
        "program": "demo",
        "members": [{"project": "provider", "rules_paths": []}],
    }

    result = run_set_up(store, document, projects=PROJECTS)

    assert result.outcome is SetUpOutcome.APPLIED


def test_unknown_provider(store: Store) -> None:
    document = {
        "program": "demo",
        "members": [
            {
                "project": "consumer",
                **RULES,
                "depends_on": [{"provider": "provider", "consumed": "from_source"}],
            }
        ],
    }

    result = _rejected(store, document)

    assert _codes(result) == [SetUpProblemCode.UNKNOWN_PROVIDER]
    assert "members.0.depends_on.0.provider" in result.problems[0].detail
    assert "provider-id" in result.problems[0].detail


def test_self_dependency(store: Store) -> None:
    document = {
        "program": "demo",
        "members": [
            {
                "project": "provider",
                **RULES,
                "depends_on": [{"provider": "provider", "consumed": "from_source"}],
            }
        ],
    }

    result = _rejected(store, document)

    assert _codes(result) == [SetUpProblemCode.SELF_DEPENDENCY]
    assert "members.0.depends_on.0.provider" in result.problems[0].detail


@pytest.mark.parametrize("field", ["authorize_allow", "authorize_deny"])
def test_unknown_authorize_item(store: Store, field: str) -> None:
    document = {
        "program": "demo",
        "members": [{"project": "provider", **RULES, field: ["no_such_item"]}],
    }

    result = _rejected(store, document)

    assert _codes(result) == [SetUpProblemCode.UNKNOWN_AUTHORIZE_ITEM]
    assert f"members.0.{field}" in result.problems[0].detail
    assert "no_such_item" in result.problems[0].detail


def test_concept_member_not_member(store: Store) -> None:
    document = {
        "program": "demo",
        "concept": {"member": "consumer", "path": "docs/concept.md"},
        "members": [{"project": "provider", **RULES}],
    }

    result = _rejected(store, document)

    assert _codes(result) == [SetUpProblemCode.CONCEPT_MEMBER_NOT_MEMBER]
    assert "concept.member" in result.problems[0].detail


def test_two_problems_in_one_request_are_both_returned(store: Store) -> None:
    document = {
        "program": "demo",
        "members": [
            {"project": "provider", "authorize_allow": ["no_such_item"]},
        ],
    }

    result = _rejected(store, document)

    assert sorted(_codes(result)) == sorted(
        [
            SetUpProblemCode.RULES_PATHS_REQUIRED,
            SetUpProblemCode.UNKNOWN_AUTHORIZE_ITEM,
        ]
    )


def test_a_rejection_against_an_existing_program_returns_its_unchanged_state(
    store: Store,
) -> None:
    run_set_up(
        store,
        {"program": "demo", "members": [{"project": "provider", **RULES}]},
        projects=PROJECTS,
    )

    result = _rejected(
        store,
        {
            "program": "demo",
            "members": [
                {"project": "provider", "rules_paths": []},
                {"project": "consumer"},
            ],
        },
    )

    assert result.program is not None
    assert [member.project_id for member in result.program.members] == ["provider-id"]
    assert result.program.members[0].rules_paths == ("CLAUDE.md",)
