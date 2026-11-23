"""`resolve_recipient` finds the active member by name or id (244, D4; 261, D6, D9).

The recipient carries only the member's id: the wake path and command come from a
checkout inside the claim (``tests/store/test_wake_on_checkout.py``)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from store.message_support import NOW, seed_members
from store.seed import insert_checkout
from store_open import open_local_store

from amoeba.operations.message_member import (
    Recipient,
    Refusal,
    recipient_of,
    resolve_recipient,
)
from amoeba.store.store import Store
from operations.wake_send_support import CHECKOUT

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
        yield opened


@pytest.mark.parametrize("reference", [KNOWN_ID, KNOWN_NAME, KNOWN_NAME.upper()])
def test_a_member_is_found_by_name_in_any_case_or_by_id(
    store: Store, reference: str
) -> None:
    assert recipient_of(store, reference) == Recipient(KNOWN_ID)


def test_a_member_with_no_checkout_here_is_still_a_recipient(store: Store) -> None:
    assert recipient_of(store, WITH_NO_CHECKOUT) == Recipient(WITH_NO_CHECKOUT)


def test_an_unknown_reference_is_refused(store: Store) -> None:
    assert isinstance(recipient_of(store, "nobody"), Refusal)


def test_the_member_is_read_in_one_transaction(
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


def test_resolve_recipient_runs_in_the_callers_transaction(store: Store) -> None:
    with store.read() as transaction:
        assert resolve_recipient(transaction, KNOWN_NAME) == Recipient(KNOWN_ID)
