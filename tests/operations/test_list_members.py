"""``list members`` reads names, origin and checkouts from the store (261 D11, D13)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from store.seed import insert_checkout
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.list_registry import MembersView, members_view
from amoeba.store.machines import ActingMachine, invite_machine, the_owner
from amoeba.store.store import Store
from operations.set_up_support import seed_member

NOW = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _view(store: Store) -> MembersView:
    return members_view(store, user_config(), program=None)


def test_two_machines_checkouts_are_listed_and_path_is_the_calling_machines(
    store: Store,
) -> None:
    seed_member(store, "demo", "forge-id", "forge", path="/local/forge")
    with store.write() as transaction:
        transaction.execute(
            "UPDATE checkouts SET wake_command = 'local-wake' "
            "WHERE member_id = 'forge-id'"
        )
        invite_machine(transaction, "beta", "f" * 64, NOW)
        beta = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'beta'"
            ).fetchone()[0]
        )
        owner = the_owner(transaction)
        local = ActingMachine(
            int(
                transaction.execute(
                    "SELECT machine_id FROM machines WHERE name = 'local'"
                ).fetchone()[0]
            ),
            owner,
        )
    store.act_as(ActingMachine(beta, owner))
    with store.write() as transaction:
        insert_checkout(
            transaction,
            member_id="forge-id",
            cf_project_id="cf-beta",
            path="/beta/forge",
            wake_command="beta-wake",
            now=NOW - timedelta(days=1),
        )

    on_beta = _view(store).members[0]
    store.act_as(local)
    on_local = _view(store).members[0]

    assert [(c.machine, c.path) for c in on_local.checkouts] == [
        ("local", "/local/forge"),
        ("beta", "/beta/forge"),
    ]
    assert (on_local.path, on_local.wake_command) == ("/local/forge", "local-wake")
    assert (on_beta.path, on_beta.wake_command) == ("/beta/forge", "beta-wake")


def test_a_member_with_no_checkout_and_one_named_by_its_id_are_both_shown(
    store: Store,
) -> None:
    seed_member(store, "demo", "5f0c1e", "5f0c1e")
    with store.write() as transaction:
        transaction.execute("DELETE FROM checkouts")

    row = _view(store).members[0]

    assert (row.name, row.project_id, row.checkouts) == ("5f0c1e", "5f0c1e", ())
    assert (row.path, row.in_context_forge) == (None, False)
