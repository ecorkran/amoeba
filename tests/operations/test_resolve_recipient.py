"""`resolve_recipient` returns the checkout path and the wake command (244, D4; 261)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from store.message_support import NOW, seed_members
from store.seed import insert_checkout
from store_open import open_local_store

from amoeba.operations.caller import acting_machine_id
from amoeba.operations.message_member import (
    Recipient,
    recipient_of,
    resolve_recipient,
)
from amoeba.store.store import Store
from operations.wake_send_support import CHECKOUT, COMMAND

KNOWN_ID = "known-project-id"
KNOWN_NAME = "known-project-name"
WITH_NO_CHECKOUT = "id-with-no-checkout"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(
                transaction,
                KNOWN_ID,
                WITH_NO_CHECKOUT,
                names={KNOWN_ID: KNOWN_NAME},
            )
            insert_checkout(
                transaction,
                member_id=KNOWN_ID,
                cf_project_id=KNOWN_ID,
                path=str(CHECKOUT),
                now=NOW,
            )
            transaction.execute(
                "UPDATE members SET wake_command = ? WHERE project_id = ?",
                (COMMAND, KNOWN_ID),
            )
        yield opened


@pytest.mark.parametrize("reference", [KNOWN_ID, KNOWN_NAME])
def test_the_path_is_returned_for_a_member_with_a_checkout_here(
    store: Store, reference: str
) -> None:
    recipient = recipient_of(store, reference)

    assert recipient == Recipient(KNOWN_ID, str(CHECKOUT), COMMAND)


def test_the_path_is_null_for_a_member_with_no_checkout_on_this_machine(
    store: Store,
) -> None:
    recipient = recipient_of(store, WITH_NO_CHECKOUT)

    assert recipient == Recipient(WITH_NO_CHECKOUT, None, None)


def test_the_first_added_checkout_here_gives_the_path(store: Store) -> None:
    with store.write() as transaction:
        insert_checkout(
            transaction,
            member_id=KNOWN_ID,
            cf_project_id="second-project",
            path="/work/second",
            now=NOW.replace(year=2027),
        )
        recipient = resolve_recipient(
            transaction, acting_machine_id(transaction), KNOWN_NAME
        )

    assert recipient == Recipient(KNOWN_ID, str(CHECKOUT), COMMAND)


def test_the_member_is_read_once_for_the_id_the_path_and_the_command(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads = 0
    real_read = store.read

    def counting() -> Any:
        nonlocal reads
        reads += 1
        return real_read()

    monkeypatch.setattr(store, "read", counting)

    recipient_of(store, KNOWN_NAME)

    assert reads == 1
