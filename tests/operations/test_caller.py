"""The caller lookup and the reference lookups, on the store (slice 261, D6)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from store.seed import insert_checkout, insert_member, insert_program
from store_open import open_local_store

from amoeba.operations.caller import (
    NotAProject,
    NotInProgram,
    find_caller,
    find_member,
    find_member_for_removal,
)
from amoeba.operations.here_document import HereCaller, HereCheckout, HereNotAProject
from amoeba.store.checkouts import delete_checkouts_of_member
from amoeba.store.machines import invite_machine
from amoeba.store.programs import remove_member
from amoeba.store.store import Store, Transaction

NOW = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)
FORGE_ID = "5f0c1e0000000000000000000000abcd"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            insert_program(
                transaction,
                program_id="demo",
                concept_member=None,
                concept_path=None,
                registered_at=NOW,
                updated_at=NOW,
            )
            _member(transaction, FORGE_ID, "Forge")
            _member(transaction, "lib-id", "lib")
            insert_checkout(
                transaction,
                member_id=FORGE_ID,
                cf_project_id="project_1_forge",
                path="/work/forge",
                now=NOW,
            )
        yield opened


def _member(transaction: Transaction, project_id: str, name: str) -> None:
    insert_member(
        transaction,
        project_id=project_id,
        program_id="demo",
        rules_paths=(),
        authorize_allow=(),
        authorize_deny=(),
        registered_at=NOW,
        updated_at=NOW,
        name=name,
    )


def _local(transaction: Transaction) -> int:
    return int(
        transaction.execute(
            "SELECT machine_id FROM machines WHERE name = 'local'"
        ).fetchone()[0]
    )


def test_the_caller_is_found_by_machine_and_project_id(store: Store) -> None:
    with store.read() as transaction:
        found = find_caller(
            transaction, _local(transaction), HereCaller(project_id="project_1_forge")
        )

    assert not isinstance(found, NotInProgram | NotAProject)
    assert found.project_id == FORGE_ID


def test_a_gathered_checkout_finds_the_caller_the_same_way(store: Store) -> None:
    here = HereCheckout(project_id="project_1_forge", name="x", path="/p", origin=None)
    with store.read() as transaction:
        found = find_caller(transaction, _local(transaction), here)

    assert not isinstance(found, NotInProgram | NotAProject)
    assert found.project_id == FORGE_ID


def test_the_same_project_id_on_another_machine_is_not_in_a_program(
    store: Store,
) -> None:
    with store.write() as transaction:
        invite_machine(transaction, "beta", "c" * 64, NOW)
        beta = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'beta'"
            ).fetchone()[0]
        )
        found = find_caller(transaction, beta, HereCaller(project_id="project_1_forge"))

    assert found == NotInProgram("project_1_forge")


def test_an_unknown_project_id_is_not_in_a_program(store: Store) -> None:
    with store.read() as transaction:
        found = find_caller(
            transaction, _local(transaction), HereCaller(project_id="project_9")
        )

    assert found == NotInProgram("project_9")


def test_a_removed_members_checkout_is_not_found(store: Store) -> None:
    with store.write() as transaction:
        remove_member(transaction, FORGE_ID, NOW)
        found = find_caller(
            transaction, _local(transaction), HereCaller(project_id="project_1_forge")
        )
        delete_checkouts_of_member(transaction, FORGE_ID)
        after = find_caller(
            transaction, _local(transaction), HereCaller(project_id="project_1_forge")
        )

    assert found == after == NotInProgram("project_1_forge")


def test_not_a_project_is_not_a_project_with_cfs_message(store: Store) -> None:
    with store.read() as transaction:
        found = find_caller(
            transaction,
            _local(transaction),
            HereNotAProject(not_a_project="no project here"),
        )

    assert found == NotAProject("no project here")


@pytest.mark.parametrize("reference", ["Forge", "forge", "FORGE", FORGE_ID])
def test_find_member_by_name_in_any_case_or_by_id(store: Store, reference: str) -> None:
    with store.read() as transaction:
        found = find_member(transaction, reference)

    assert found is not None
    assert found.project_id == FORGE_ID


def test_find_member_of_an_unknown_reference_is_none(store: Store) -> None:
    with store.read() as transaction:
        assert find_member(transaction, "nobody") is None


def test_a_removed_member_is_found_for_removal_only_by_id(store: Store) -> None:
    with store.write() as transaction:
        remove_member(transaction, FORGE_ID, NOW)

        assert find_member(transaction, "Forge") is None
        assert find_member(transaction, FORGE_ID) is None
        assert find_member_for_removal(transaction, "Forge") is None
        by_id = find_member_for_removal(transaction, FORGE_ID)

    assert by_id is not None
    assert by_id.removed_at is not None


def test_an_active_member_is_found_for_removal_by_name_or_id(store: Store) -> None:
    with store.read() as transaction:
        by_name = find_member_for_removal(transaction, "lib")
        by_id = find_member_for_removal(transaction, "lib-id")

    assert by_name is not None
    assert by_id is not None
    assert by_name.removed_at is None
