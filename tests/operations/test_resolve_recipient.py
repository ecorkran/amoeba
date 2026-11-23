"""`resolve_recipient` returns the checkout path and the wake command (244, D4)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import DEFAULT_WORKTREE
from store.message_support import seed_members
from store_open import open_local_store

from amoeba.operations.message_member import Recipient, resolve_recipient
from amoeba.store.store import Store
from operations.set_up_support import FakeCf
from operations.wake_send_support import CHECKOUT, COMMAND

KNOWN_ID = "known-project-id"
KNOWN_NAME = "known-project-name"
UNKNOWN_TO_CF = "id-context-forge-does-not-know"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, KNOWN_ID, UNKNOWN_TO_CF)
            transaction.execute(
                "UPDATE members SET wake_command = ? WHERE project_id = ?",
                (COMMAND, KNOWN_ID),
            )
        yield opened


def _cf() -> FakeCf:
    return FakeCf(directory_fixture=DEFAULT_WORKTREE, projects=[(KNOWN_ID, KNOWN_NAME)])


@pytest.mark.parametrize("reference", [KNOWN_ID, KNOWN_NAME])
def test_the_path_is_returned_for_a_reference_context_forge_knows(
    store: Store, reference: str
) -> None:
    recipient = resolve_recipient(store, reference, _cf())

    assert recipient == Recipient(KNOWN_ID, str(CHECKOUT), COMMAND)


def test_the_path_is_null_for_a_reference_read_as_an_id(store: Store) -> None:
    recipient = resolve_recipient(store, UNKNOWN_TO_CF, _cf())

    assert recipient == Recipient(UNKNOWN_TO_CF, None, None)


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

    resolve_recipient(store, KNOWN_NAME, _cf())

    assert reads == 1
