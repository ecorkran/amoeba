"""``add`` through the engine with the gathered checkout (slice 261, D5, D7)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.add import add as add_operation
from amoeba.operations.caller import find_member
from amoeba.operations.here_document import HereCheckout
from amoeba.operations.set_up_models import (
    SetUpOutcome,
    SetUpProblemCode,
    SetUpResult,
)
from amoeba.store.checkouts import checkouts_of_member
from amoeba.store.store import Store
from amoeba.store.vocabulary import Door
from operations.add_placed import add
from operations.rm_placed import rm
from operations.set_up_support import (
    DIRECTORY,
    RECORDED_NAME,
    FakeCf,
    seed_member,
)

ORIGIN = "github.com/org/forge"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _add(
    store: Store, document: dict[str, Any], fixture: str = DEFAULT_WORKTREE
) -> SetUpResult:
    return add(
        store,
        user_config(),
        document,
        directory=DIRECTORY,
        run=FakeCf(directory_fixture=fixture),
        door=Door.CLI,
    )


def _from(
    store: Store, project: str, name: str, document: dict[str, Any], origin: str | None
) -> SetUpResult:
    here = HereCheckout(
        project_id=project, name=name, path=f"/work/{project}", origin=origin
    )
    return add_operation(store, user_config(), document, here=here)


def _codes(result: SetUpResult) -> list[SetUpProblemCode]:
    return [problem.code for problem in result.problems]


def test_project_and_an_all_named_bulk_file_work_from_a_non_project_directory(
    store: Store,
) -> None:
    seed_member(store, "demo", "other-id", "other-repo")
    seed_member(store, "demo", "lib-id", "lib")

    single = _add(
        store,
        {"project": "other-repo", "authorize_deny": ["push"]},
        OUTSIDE_ANY_PROJECT,
    )
    bulk = _add(
        store,
        {"bulk": {"program": "demo", "members": [{"project": "lib"}]}},
        OUTSIDE_ANY_PROJECT,
    )

    assert single.outcome is SetUpOutcome.APPLIED
    assert single.working_directory is None
    assert bulk.working_directory is None


def test_project_with_a_wake_command_is_malformed(store: Store) -> None:
    seed_member(store, "demo", "other-id", "other-repo")

    result = _add(store, {"project": "other-repo", "wake_command": "agent"})

    assert result.outcome is SetUpOutcome.REJECTED
    assert _codes(result) == [SetUpProblemCode.MALFORMED]
    assert "its own checkout" in result.problems[0].detail


def test_two_bulk_entries_that_name_no_member_are_malformed(store: Store) -> None:
    result = _add(store, {"bulk": {"program": "demo", "members": [{}, {}]}})

    assert _codes(result) == [SetUpProblemCode.MALFORMED]
    assert "only one entry" in result.problems[0].detail


def test_a_bulk_entry_for_a_non_member_is_not_a_member_naming_the_way_on(
    store: Store,
) -> None:
    result = _add(
        store, {"bulk": {"program": "demo", "members": [{"project": "stranger"}]}}
    )

    assert _codes(result) == [SetUpProblemCode.NOT_A_MEMBER]
    assert "amoeba add" in result.problems[0].detail


def test_name_renames_the_member_the_checkout_is_on_record_for(store: Store) -> None:
    _add(store, {})

    result = _add(store, {"name": "renamed"})

    assert result.outcome is SetUpOutcome.APPLIED
    assert result.changes == (f"updated member {RECORDED_NAME} is now named renamed",)
    with store.read() as transaction:
        assert find_member(transaction, "renamed") is not None
        assert find_member(transaction, RECORDED_NAME) is None


def test_name_taken_is_a_rejection_that_writes_nothing(store: Store) -> None:
    seed_member(store, "demo", "other-id", "taken")

    result = _add(store, {"name": "taken"})

    assert _codes(result) == [SetUpProblemCode.NAME_TAKEN]
    with store.read() as transaction:
        assert find_member(transaction, RECORDED_NAME) is None


def test_a_second_checkout_with_the_same_origin_attaches_to_the_one_member(
    store: Store,
) -> None:
    first = _from(store, "cf-alpha", "forge", {}, ORIGIN)
    second = _from(store, "cf-beta", "forge", {}, ORIGIN)

    assert first.outcome is SetUpOutcome.APPLIED
    assert second.changes == ("added checkout /work/cf-beta of forge",)
    with store.read() as transaction:
        member = find_member(transaction, "forge")
        assert member is not None
        assert len(checkouts_of_member(transaction, member.project_id)) == 2
        assert transaction.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 1


def test_attach_to_gives_a_checkout_back_to_a_member_with_none(store: Store) -> None:
    seed_member(store, "demo", "gone-id", "gone")
    with store.write() as transaction:
        transaction.execute("DELETE FROM checkouts")

    result = _from(store, "cf-new", "anything", {"attach_to": "gone"}, None)

    assert result.outcome is SetUpOutcome.APPLIED
    assert "added checkout /work/cf-new of gone" in result.changes
    with store.read() as transaction:
        assert len(checkouts_of_member(transaction, "gone-id")) == 1


def test_rm_checkout_then_new_member_makes_a_second_member_for_that_checkout(
    store: Store,
) -> None:
    _from(store, "cf-alpha", "forge", {}, ORIGIN)
    removed = rm(
        store,
        user_config(),
        {"checkout": "/work/cf-alpha"},
        directory=DIRECTORY,
        run=FakeCf(directory_fixture=DEFAULT_WORKTREE),
    )
    assert removed.outcome is SetUpOutcome.APPLIED

    again = _from(
        store, "cf-alpha", "forge", {"new_member": True, "name": "forge-two"}, ORIGIN
    )

    # The first member keeps the origin, so the new one has none recorded.
    assert again.outcome is SetUpOutcome.APPLIED
    with store.read() as transaction:
        first = find_member(transaction, "forge")
        second = find_member(transaction, "forge-two")
    assert first is not None
    assert second is not None
    assert first.origin == ORIGIN
    assert second.origin is None
    assert first.project_id != second.project_id
