"""A wake claims from a checkout of the recipient on the acting machine (261 D9)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.machines import ActingMachine, invite_machine, the_owner
from amoeba.store.store import Store, Transaction
from amoeba.store.wakes import WakeScope, can_wake, claim_wake, get_wake
from store.message_support import ADDRESSEE, NOW, SENDER, seed_members
from store.seed import insert_checkout
from store.wake_support import (
    COMMAND,
    LIMITS,
    LOG_DIRECTORY,
    claim,
    seed_waking_member,
)

LATER = NOW + timedelta(hours=1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER)
            seed_waking_member(transaction, ADDRESSEE, None, directory=None)
        yield opened


def _add(
    transaction: Transaction,
    cf_id: str,
    path: str,
    command: str | None,
    *,
    when: object = NOW,
) -> None:
    insert_checkout(
        transaction,
        member_id=ADDRESSEE,
        cf_project_id=cf_id,
        path=path,
        wake_command=command,
        now=when,  # type: ignore[arg-type]
    )


def test_of_two_checkouts_here_the_claim_uses_the_one_with_a_command(
    store: Store,
) -> None:
    with store.write() as transaction:
        _add(transaction, "cf-plain", "/work/plain", None)
        _add(transaction, "cf-waking", "/work/waking", COMMAND, when=LATER)
        wake = claim(transaction, "w1")

    assert wake is not None
    assert (wake.directory, wake.command) == ("/work/waking", COMMAND)


def test_of_two_checkouts_with_a_command_the_first_added_is_used(store: Store) -> None:
    with store.write() as transaction:
        _add(transaction, "cf-late", "/work/late", "later-command", when=LATER)
        _add(transaction, "cf-first", "/work/first", COMMAND)
        wake = claim(transaction, "w1")

    assert wake is not None
    assert (wake.directory, wake.command) == ("/work/first", COMMAND)


def test_a_member_with_no_checkout_gets_no_claim(store: Store) -> None:
    with store.write() as transaction:
        assert claim(transaction, "w1") is None
        assert not can_wake(transaction, ADDRESSEE, NOW, LIMITS)


def test_the_wake_row_carries_the_checkouts_path_and_command(store: Store) -> None:
    with store.write() as transaction:
        _add(transaction, "cf-1", "/work/checkout", COMMAND)
        claimed = claim_wake(transaction, ADDRESSEE, NOW, LIMITS, "w9", "/logs/w9")
        row = get_wake(transaction, "w9")

    assert claimed is not None
    assert row is not None
    assert (row.directory, row.command, row.log_stem) == (
        "/work/checkout",
        COMMAND,
        "/logs/w9",
    )
    assert LOG_DIRECTORY  # the support's log stem is not used here


def test_a_command_only_on_another_machine_is_seen_by_the_wider_scope_only(
    store: Store,
) -> None:
    with store.write() as transaction:
        invite_machine(transaction, "beta", "e" * 64, NOW)
        beta = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'beta'"
            ).fetchone()[0]
        )
        owner = the_owner(transaction)
    store.act_as(ActingMachine(beta, owner))
    with store.write() as transaction:
        _add(transaction, "cf-beta", "/beta/work", COMMAND)
    with store.read() as transaction:
        local = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'local'"
            ).fetchone()[0]
        )
    store.act_as(ActingMachine(local, owner))

    with store.write() as transaction:
        assert claim(transaction, "w1") is None
        assert not can_wake(
            transaction, ADDRESSEE, NOW, LIMITS, WakeScope.ACTING_MACHINE
        )
        assert can_wake(transaction, ADDRESSEE, NOW, LIMITS, WakeScope.ALL_MACHINES)
