"""Lookups by name and ``origin``, and the name rules (slice 261, D1 to D4)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.member_names import (
    active_member_by_name,
    active_member_by_origin,
    name_is_other_members_id,
    removed_member_by_origin,
    set_member_name,
    set_member_origin,
)
from amoeba.store.programs import get_member, remove_member
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import MEMBER_NAME_MAX_LENGTH, is_member_name
from store.seed import insert_member, insert_program

NOW = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)


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
        yield opened


def _member(
    transaction: Transaction, project_id: str, name: str, origin: str | None = None
) -> None:
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
        origin=origin,
    )


def test_a_name_is_found_in_any_case(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, "id-1", "Forge")
        found = active_member_by_name(transaction, "fORGE")
        missing = active_member_by_name(transaction, "other")

    assert missing is None
    assert found is not None
    assert (found.project_id, found.name) == ("id-1", "Forge")


def test_a_removed_member_is_not_found_by_name_or_origin(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, "id-1", "forge", "host/org/repo")
        remove_member(transaction, "id-1", NOW)

        assert active_member_by_name(transaction, "forge") is None
        assert active_member_by_origin(transaction, "host/org/repo") is None


def test_an_active_member_is_found_by_origin(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, "id-1", "forge", "host/org/repo")
        found = active_member_by_origin(transaction, "host/org/repo")

    assert found is not None
    assert found.origin == "host/org/repo"


def test_the_most_recently_removed_member_with_an_origin_is_returned(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, "id-1", "forge", "host/org/repo")
        remove_member(transaction, "id-1", NOW)
        _member(transaction, "id-2", "forge-2", "host/org/repo")
        remove_member(transaction, "id-2", NOW + timedelta(hours=1))
        _member(transaction, "id-3", "forge-3", "host/org/repo")

        found = removed_member_by_origin(transaction, "host/org/repo")

    assert found is not None
    assert found.project_id == "id-2"


def test_a_name_that_is_another_members_id_is_found_in_any_case(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, "ABC123", "forge")
        _member(transaction, "id-2", "lib")
        remove_member(transaction, "id-2", NOW)

        assert name_is_other_members_id(transaction, "abc123", "id-2")
        assert name_is_other_members_id(transaction, "id-2", "ABC123")
        assert not name_is_other_members_id(transaction, "ABC123", "ABC123")
        assert not name_is_other_members_id(transaction, "nobody", "ABC123")


def test_a_name_and_an_origin_are_set_and_cleared(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, "id-1", "forge")
        set_member_name(transaction, "id-1", "forge-2", NOW + timedelta(days=1))
        set_member_origin(transaction, "id-1", "host/org/repo", NOW)
        member = get_member(transaction, "id-1")
        set_member_origin(transaction, "id-1", None, NOW)
        cleared = get_member(transaction, "id-1")

    assert member is not None
    assert (member.name, member.origin) == ("forge-2", "host/org/repo")
    assert cleared is not None
    assert cleared.origin is None


@pytest.mark.parametrize(
    "name",
    ["forge", "Forge-2", "a", "0abc", "a.b_c-d", "a" * MEMBER_NAME_MAX_LENGTH],
)
def test_valid_member_names(name: str) -> None:
    assert is_member_name(name)


@pytest.mark.parametrize(
    "name",
    ["", "a:b", ".hidden", "-x", "a b", "a/b", "a" * (MEMBER_NAME_MAX_LENGTH + 1)],
)
def test_invalid_member_names(name: str) -> None:
    assert not is_member_name(name)
