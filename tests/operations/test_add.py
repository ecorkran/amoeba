"""``add``: program choice and the guards through the new door (slice 229, D4, D5)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import (
    DEFAULT_WORKTREE,
    OUTSIDE_ANY_PROJECT,
    fake_cf_run,
    fixture_document,
)
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.add import NOT_A_PROJECT_DETAIL
from amoeba.operations.add import add as add_operation
from amoeba.operations.errors import ContextForgeError
from amoeba.operations.here_document import HereCheckout
from amoeba.operations.names import Door
from amoeba.operations.set_up_models import (
    SetUpOutcome,
    SetUpProblemCode,
    SetUpResult,
)
from amoeba.store.store import Store
from operations.add_placed import add
from operations.set_up_support import (
    DIRECTORY,
    RECORDED_NAME,
    FakeCf,
    row_counts,
    run_set_up,
    seed_member,
)

RECORDED_PATH = str(fixture_document(DEFAULT_WORKTREE)["projectPath"])


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _add(
    store: Store,
    document: dict[str, Any] | None = None,
    *,
    directory_fixture: str = DEFAULT_WORKTREE,
) -> SetUpResult:
    return add(
        store,
        user_config(),
        document or {},
        directory=DIRECTORY,
        run=FakeCf(directory_fixture=directory_fixture),
        door=Door.CLI,
    )


def _codes(result: SetUpResult) -> list[SetUpProblemCode]:
    return [problem.code for problem in result.problems]


def _add_from(
    store: Store, project_id: str, name: str, document: dict[str, Any]
) -> SetUpResult:
    """``add`` run in another repo's checkout."""
    here = HereCheckout(
        project_id=project_id, name=name, path=f"/work/{name}", origin=None
    )
    return add_operation(store, user_config(), document, here=here)


def test_the_first_run_creates_a_program_named_for_the_cf_project(
    store: Store,
) -> None:
    result = _add(store)

    assert result.outcome is SetUpOutcome.APPLIED
    assert result.changes == (
        f"added program {RECORDED_NAME}",
        f"added member {RECORDED_NAME}",
        f"added checkout {RECORDED_PATH} of {RECORDED_NAME}",
    )
    assert result.program is not None
    assert result.program.program_id == RECORDED_NAME


def test_a_second_repo_joins_a_named_program(store: Store) -> None:
    _add(store, {"program": "group"})

    result = _add_from(store, "other-id", "other-repo", {"program": "group"})

    assert result.changes == (
        "added member other-repo",
        "added checkout /work/other-repo of other-repo",
    )
    assert result.program is not None
    assert {m.name for m in result.program.members} == {RECORDED_NAME, "other-repo"}


def test_a_repeat_is_unchanged(store: Store) -> None:
    _add(store)
    before = row_counts(store)

    result = _add(store)

    assert result.outcome is SetUpOutcome.UNCHANGED
    assert row_counts(store) == before


def test_a_registered_member_keeps_its_program_when_none_is_given(
    store: Store,
) -> None:
    _add(store, {"program": "group"})

    result = _add(store, {"authorize_deny": ["push"]})

    assert result.changes == (f"updated member {RECORDED_NAME}",)
    assert result.program is not None
    assert result.program.program_id == "group"
    assert row_counts(store)["programs"] == 1


def test_a_program_that_already_exists_is_joined_without_creating_one(
    store: Store,
) -> None:
    seed_member(store, "group", "other-id", "other-repo")

    result = _add(store, {"program": "group"})

    assert result.changes == (
        f"added member {RECORDED_NAME}",
        f"added checkout {RECORDED_PATH} of {RECORDED_NAME}",
    )
    assert row_counts(store)["programs"] == 1


def test_a_program_named_like_the_project_is_joined_not_created(
    store: Store,
) -> None:
    seed_member(store, RECORDED_NAME, "other-id", "other-repo")

    result = _add(store)

    assert result.changes == (
        f"added member {RECORDED_NAME}",
        f"added checkout {RECORDED_PATH} of {RECORDED_NAME}",
    )


def test_a_directory_outside_any_project_is_rejected_with_the_fix_and_writes_nothing(
    store: Store,
) -> None:
    result = _add(store, directory_fixture=OUTSIDE_ANY_PROJECT)

    assert result.outcome is SetUpOutcome.REJECTED
    assert _codes(result) == [SetUpProblemCode.NOT_A_PROJECT]
    assert NOT_A_PROJECT_DETAIL in result.problems[0].detail
    # The fix belongs to the door (the CLI renderer), not the operations layer.
    assert "cf init" not in result.problems[0].detail
    assert "--project" not in result.problems[0].detail
    assert row_counts(store) == {"programs": 0, "members": 0, "dependency_pairs": 0}


def test_a_project_that_is_no_member_is_not_a_member_naming_the_way_on(
    store: Store,
) -> None:
    result = _add(store, {"project": "ghost"})

    assert result.outcome is SetUpOutcome.REJECTED
    assert _codes(result) == [SetUpProblemCode.NOT_A_MEMBER]
    assert result.problems[0].detail.startswith("project 'ghost': no member")
    assert "amoeba add" in result.problems[0].detail
    assert row_counts(store) == {"programs": 0, "members": 0, "dependency_pairs": 0}


def test_a_member_of_another_program_is_refused(store: Store) -> None:
    _add(store, {"program": "one"})

    result = _add(store, {"program": "two"})

    assert _codes(result) == [SetUpProblemCode.MEMBER_OF_OTHER_PROGRAM]


def test_a_provider_that_is_not_a_member_is_not_a_member(store: Store) -> None:
    result = _add(store, {"depends_on": [{"provider": "lib"}]})

    assert _codes(result) == [SetUpProblemCode.NOT_A_MEMBER]
    assert "lib" in result.problems[0].detail


def test_a_dependency_on_itself_is_refused(store: Store) -> None:
    _add(store)

    result = _add(store, {"depends_on": [{"provider": RECORDED_NAME}]})

    assert _codes(result) == [SetUpProblemCode.SELF_DEPENDENCY]


def test_a_dependency_without_a_mode_is_stored_with_the_configs_default(
    store: Store,
) -> None:
    seed_member(store, "group", "lib-id", "lib")

    result = _add(store, {"program": "group", "depends_on": [{"provider": "lib"}]})

    assert result.program is not None
    consumer = next(m for m in result.program.members if m.project_id != "lib-id")
    assert [(d.provider, d.consumed.value) for d in consumer.depends_on] == [
        ("lib-id", user_config().default_consumed.value)
    ]


def test_an_unknown_authorize_item_is_refused(store: Store) -> None:
    result = _add(store, {"authorize_allow": ["no_such_item"]})

    assert _codes(result) == [SetUpProblemCode.UNKNOWN_AUTHORIZE_ITEM]


def test_a_concept_member_that_is_not_in_the_program_is_refused(store: Store) -> None:
    seed_member(store, "elsewhere", "other-id", "other-repo")

    result = _add(
        store,
        {
            "program": "group",
            "concept": {"member": "other-repo", "path": "docs/concept.md"},
        },
    )

    assert _codes(result) == [SetUpProblemCode.CONCEPT_MEMBER_NOT_MEMBER]


def test_a_concept_member_that_is_no_member_is_not_a_member(store: Store) -> None:
    result = _add(
        store, {"concept": {"member": "other-repo", "path": "docs/concept.md"}}
    )

    assert _codes(result) == [SetUpProblemCode.NOT_A_MEMBER]


def test_bulk_and_single_fields_together_are_malformed(store: Store) -> None:
    result = _add(store, {"bulk": {"program": "p"}, "project": "other-repo"})

    assert _codes(result) == [SetUpProblemCode.MALFORMED]
    assert row_counts(store)["programs"] == 0


def test_cf_failing_raises_and_writes_nothing(store: Store) -> None:
    with pytest.raises(ContextForgeError):
        add(
            store,
            user_config(),
            {},
            directory=DIRECTORY,
            run=fake_cf_run(None),
            door=Door.CLI,
        )

    assert row_counts(store)["members"] == 0


def test_a_bulk_request_gives_the_result_set_up_gives_for_the_same_document(
    tmp_path: Path,
) -> None:
    document: dict[str, Any] = {
        "program": "group",
        "members": [
            {"project": "other-repo", "rules_paths": ["CLAUDE.md"]},
            {"project": "lib", "depends_on": []},
        ],
    }
    with (
        open_local_store(tmp_path / "a.sqlite3") as via_add,
        open_local_store(tmp_path / "b.sqlite3") as via_set_up,
    ):
        for opened in (via_add, via_set_up):
            seed_member(opened, "group", "other-id", "other-repo")
            seed_member(opened, "group", "lib-id", "lib")
        added = _add(via_add, {"bulk": document})
        set_up_result = run_set_up(via_set_up, document)

    assert added == set_up_result
    assert added.outcome is SetUpOutcome.APPLIED


@pytest.mark.parametrize(
    "document",
    [
        {"rules_paths": ["CLAUDE.md"], "rules_default": True},
        {"authorize_allow": ["push"], "authorize_deny": ["push"]},
        {"bulk": None},
    ],
)
def test_an_invalid_single_member_or_null_bulk_request_is_malformed(
    store: Store, document: dict[str, Any]
) -> None:
    result = _add(store, document)

    assert result.outcome is SetUpOutcome.REJECTED
    assert _codes(result) == [SetUpProblemCode.MALFORMED]
    assert row_counts(store) == {"programs": 0, "members": 0, "dependency_pairs": 0}
