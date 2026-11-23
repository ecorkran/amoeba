"""Checkout reads, deletes and the wake command (slice 261, D2, D7, D8, D9)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.checkouts import (
    checkout_at,
    checkouts_of_member,
    checkouts_on_machine,
    delete_checkouts_at_path,
    delete_checkouts_of_member,
    delete_checkouts_on_machine,
    first_checkout_on,
    set_checkout_wake_command,
)
from amoeba.store.errors import StoreError
from amoeba.store.machines import ActingMachine, invite_machine, the_owner
from amoeba.store.store import Store, Transaction
from store.seed import insert_checkout, insert_member, insert_program

NOW = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)


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
            for member in ("forge", "lib"):
                insert_member(
                    transaction,
                    project_id=member,
                    program_id="demo",
                    rules_paths=(),
                    authorize_allow=(),
                    authorize_deny=(),
                    registered_at=NOW,
                    updated_at=NOW,
                )
        yield opened


def _machine_id(transaction: Transaction, name: str) -> int:
    row = transaction.execute(
        "SELECT machine_id FROM machines WHERE name = ?", (name,)
    ).fetchone()
    return int(row[0])


def _local_machine_id(transaction: Transaction) -> int:
    return _machine_id(transaction, "local")


def _add(
    transaction: Transaction,
    member: str,
    cf_id: str,
    path: str,
    *,
    at: datetime = NOW,
    command: str | None = None,
) -> None:
    insert_checkout(
        transaction,
        member_id=member,
        cf_project_id=cf_id,
        path=path,
        wake_command=command,
        now=at,
    )


def test_a_checkout_is_read_back_by_machine_and_context_forge_id(store: Store) -> None:
    with store.write() as transaction:
        _add(transaction, "forge", "cf-1", "/work/forge", command="make go")
    with store.read() as transaction:
        machine_id = _local_machine_id(transaction)
        found = checkout_at(transaction, machine_id, "cf-1")
        missing = checkout_at(transaction, machine_id, "cf-2")

    assert missing is None
    assert found is not None
    assert (found.member_id, found.path, found.wake_command) == (
        "forge",
        "/work/forge",
        "make go",
    )
    assert found.machine_id == machine_id
    assert found.added_at == found.updated_at == NOW


def test_checkouts_come_back_in_the_order_they_were_added(store: Store) -> None:
    with store.write() as transaction:
        _add(transaction, "forge", "cf-late", "/late", at=LATER)
        _add(transaction, "forge", "cf-first", "/first", at=NOW)
        _add(transaction, "forge", "cf-tie", "/tie", at=NOW)
        _add(transaction, "lib", "cf-lib", "/lib")
    with store.read() as transaction:
        machine_id = _local_machine_id(transaction)
        of_member = checkouts_of_member(transaction, "forge")
        on_machine = checkouts_on_machine(transaction, machine_id)

    assert [c.path for c in of_member] == ["/first", "/tie", "/late"]
    assert [c.path for c in on_machine] == ["/first", "/tie", "/lib", "/late"]


def test_first_checkout_on_is_per_machine(store: Store) -> None:
    with store.write() as transaction:
        _add(transaction, "forge", "cf-2", "/second", at=LATER)
        _add(transaction, "forge", "cf-1", "/first", at=NOW)
        local = _local_machine_id(transaction)
        invite_machine(transaction, "beta", "a" * 64, NOW)
        beta = _machine_id(transaction, "beta")
    with store.read() as transaction:
        on_local = first_checkout_on(transaction, "forge", local)
        on_beta = first_checkout_on(transaction, "forge", beta)

    assert on_local is not None
    assert on_local.path == "/first"
    assert on_beta is None


@pytest.mark.parametrize(
    ("stored", "given"),
    [
        ("/work/forge", "/work/forge"),
        ("/work/forge", "/work/forge/"),
        ("/work/forge/", "/work/forge"),
        ("/work/forge/", "/work/forge//"),
    ],
)
def test_delete_at_path_ignores_trailing_slashes_on_either_side(
    store: Store, stored: str, given: str
) -> None:
    with store.write() as transaction:
        _add(transaction, "forge", "cf-1", stored)
        _add(transaction, "lib", "cf-2", "/work/lib")
        machine_id = _local_machine_id(transaction)
        deleted = delete_checkouts_at_path(transaction, machine_id, given)
        remaining = checkouts_on_machine(transaction, machine_id)

    assert deleted == 1
    assert [c.path for c in remaining] == ["/work/lib"]


def test_two_rows_at_one_path_are_both_deleted(store: Store) -> None:
    with store.write() as transaction:
        _add(transaction, "forge", "cf-old", "/work/forge")
        _add(transaction, "forge", "cf-new", "/work/forge")
        machine_id = _local_machine_id(transaction)

        assert delete_checkouts_at_path(transaction, machine_id, "/work/forge") == 2
        assert delete_checkouts_at_path(transaction, machine_id, "/work/forge") == 0


def test_deletes_by_member_and_by_machine(store: Store) -> None:
    with store.write() as transaction:
        _add(transaction, "forge", "cf-1", "/a")
        _add(transaction, "lib", "cf-2", "/b")
        assert delete_checkouts_of_member(transaction, "forge") == 1
        assert [c.member_id for c in checkouts_of_member(transaction, "lib")] == ["lib"]
        machine_id = _local_machine_id(transaction)
        assert delete_checkouts_on_machine(transaction, machine_id) == 1
        assert checkouts_on_machine(transaction, machine_id) == ()


def test_the_wake_command_is_set_and_cleared_on_the_acting_machine(
    store: Store,
) -> None:
    with store.write() as transaction:
        _add(transaction, "forge", "cf-1", "/a")
        machine_id = _local_machine_id(transaction)
        checkout = checkout_at(transaction, machine_id, "cf-1")
        assert checkout is not None

        set_checkout_wake_command(transaction, checkout.checkout_id, "go", LATER)
        after_set = checkout_at(transaction, machine_id, "cf-1")
        set_checkout_wake_command(transaction, checkout.checkout_id, None, LATER)
        after_clear = checkout_at(transaction, machine_id, "cf-1")

    assert after_set is not None
    assert (after_set.wake_command, after_set.updated_at) == ("go", LATER)
    assert after_clear is not None
    assert after_clear.wake_command is None


def test_a_wake_command_on_another_machines_checkout_raises_and_changes_nothing(
    tmp_path: Path, store: Store
) -> None:
    with store.write() as transaction:
        _add(transaction, "forge", "cf-1", "/a", command="keep")
        machine_id = _local_machine_id(transaction)
        checkout = checkout_at(transaction, machine_id, "cf-1")
        assert checkout is not None
        invite_machine(transaction, "beta", "b" * 64, NOW)
        beta = ActingMachine(_machine_id(transaction, "beta"), the_owner(transaction))
    store.act_as(beta)

    with pytest.raises(StoreError, match="'local'.*'beta'"), store.write() as tx:
        set_checkout_wake_command(tx, checkout.checkout_id, "other", LATER)

    with store.read() as transaction:
        kept = checkout_at(transaction, machine_id, "cf-1")
    assert kept is not None
    assert kept.wake_command == "keep"
