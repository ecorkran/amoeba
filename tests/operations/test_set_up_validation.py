"""``set_up`` validation and reference resolution: rejections before the checks."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run
from user_configs import user_config

from amoeba.operations.members import ContextForgeError
from amoeba.operations.set_up import SetUpProblemCode, SetUpResult, set_up
from amoeba.operations.set_up_models import SetUpOutcome
from amoeba.store.store import Store
from operations.set_up_support import (
    DIRECTORY,
    RECORDED_ID,
    RECORDED_NAME,
    row_counts,
    run_set_up,
)

EMPTY = {"programs": 0, "members": 0, "dependency_pairs": 0}
PROJECTS = [("provider-id", "provider")]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _member(**fields: Any) -> dict[str, Any]:
    return {"rules_paths": ["CLAUDE.md"], **fields}


def _rejected(store: Store, document: object, **options: Any) -> SetUpResult:
    result = run_set_up(store, document, **options)
    assert result.outcome is SetUpOutcome.REJECTED
    assert result.changes == ()
    assert row_counts(store) == EMPTY
    return result


@pytest.mark.parametrize(
    ("document", "named"),
    [
        (["not", "a", "mapping"], "document"),
        ("just text", "document"),
        ({"members": [_member()]}, "program"),
        ({"program": "demo", "surprise": 1}, "surprise"),
        ({"program": "demo", "members": [_member(surprise=1)]}, "members.0.surprise"),
        (
            {"program": "demo", "members": [_member(rules_paths=["/etc/passwd"])]},
            "members.0.rules_paths.0",
        ),
        (
            {"program": "demo", "members": [_member(rules_paths=["../x.md"])]},
            "members.0.rules_paths.0",
        ),
        (
            {"program": "demo", "concept": {"member": "m", "path": "/abs/c.md"}},
            "concept.path",
        ),
        (
            {"program": "demo", "concept": {"member": "m", "path": "docs/*.md"}},
            "concept.path",
        ),
        (
            {
                "program": "demo",
                "members": [_member(authorize_allow=["push"], authorize_deny=["push"])],
            },
            "authorize_allow",
        ),
        (
            {
                "program": "demo",
                "members": [_member(depends_on=[{"provider": "p", "consumed": "x"}])],
            },
            "members.0.depends_on.0.consumed",
        ),
    ],
)
def test_malformed_request_names_the_field(
    store: Store, document: object, named: str
) -> None:
    result = _rejected(store, document)

    assert result.working_directory is None
    assert result.program is None
    assert {problem.code for problem in result.problems} == {SetUpProblemCode.MALFORMED}
    assert any(named in problem.detail for problem in result.problems)


def test_two_malformed_fields_are_both_listed(store: Store) -> None:
    result = _rejected(
        store, {"program": "demo", "surprise": 1, "members": [_member(extra=1)]}
    )

    assert len(result.problems) == 2


def test_a_member_listed_twice_by_name_and_id_is_malformed(store: Store) -> None:
    document = {
        "program": "demo",
        "members": [
            _member(project="provider"),
            _member(project="provider-id"),
        ],
    }

    result = _rejected(store, document, projects=PROJECTS)

    assert [problem.code for problem in result.problems] == [SetUpProblemCode.MALFORMED]
    assert "members.1.project" in result.problems[0].detail
    assert "members.0" in result.problems[0].detail


def test_a_member_named_by_the_working_directory_and_by_name_is_malformed(
    store: Store,
) -> None:
    document = {
        "program": "demo",
        "members": [_member(), _member(project=RECORDED_NAME)],
    }

    result = _rejected(store, document)

    assert result.problems[0].code is SetUpProblemCode.MALFORMED


def test_a_bad_reference_is_not_a_project(store: Store) -> None:
    document = {"program": "demo", "members": [_member(project="no-such-project")]}

    result = _rejected(store, document)

    assert [problem.code for problem in result.problems] == [
        SetUpProblemCode.NOT_A_PROJECT
    ]
    assert "members.0.project" in result.problems[0].detail


def test_a_bad_provider_and_concept_member_are_not_a_project(store: Store) -> None:
    document = {
        "program": "demo",
        "concept": {"member": "ghost", "path": "docs/concept.md"},
        "members": [
            _member(depends_on=[{"provider": "phantom", "consumed": "from_source"}])
        ],
    }

    result = _rejected(store, document)

    details = " ".join(problem.detail for problem in result.problems)
    assert "concept.member" in details
    assert "members.0.depends_on.0.provider" in details
    assert {problem.code for problem in result.problems} == {
        SetUpProblemCode.NOT_A_PROJECT
    }


def test_an_omitted_project_with_a_non_project_directory_is_not_a_project(
    store: Store,
) -> None:
    result = _rejected(
        store,
        {"program": "demo", "members": [_member()]},
        directory_fixture=OUTSIDE_ANY_PROJECT,
    )

    assert [problem.code for problem in result.problems] == [
        SetUpProblemCode.NOT_A_PROJECT
    ]
    assert "working directory" in result.problems[0].detail


def test_a_cf_failure_raises_before_anything_is_written(store: Store) -> None:
    with pytest.raises(ContextForgeError):
        set_up(
            store,
            user_config(),
            {"program": "demo", "members": [_member()]},
            directory=DIRECTORY,
            run=fake_cf_run(None),
        )

    assert row_counts(store) == EMPTY


def test_an_omitted_project_uses_the_working_directorys_project(store: Store) -> None:
    result = run_set_up(store, {"program": "demo", "members": [_member()]})

    assert result.outcome is SetUpOutcome.APPLIED
    assert result.program is not None
    assert [member.project_id for member in result.program.members] == [RECORDED_ID]
