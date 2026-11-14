"""Release writers and ``release_for_commit`` (slice 227, D2)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.store import releases
from amoeba.store.errors import StoreIntegrityError
from amoeba.store.models import Release
from amoeba.store.store import Store
from store.release_support import (
    FULL_HASH,
    OTHER_HASH,
    OTHER_PROVIDER,
    PROVIDER,
    at,
    seed_members,
)

TOUCHED = ("cli", "store")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _insert(
    store: Store, *, commit: str = FULL_HASH, version: str | None = None, hours: int = 1
) -> None:
    with store.write() as transaction:
        releases.insert_release(
            transaction, PROVIDER, commit, version, "first text", TOUCHED, at(hours)
        )


def _stored(store: Store, commit: str = FULL_HASH) -> Release:
    with store.read() as transaction:
        found = releases.release_for_commit(transaction, PROVIDER, commit)
    assert found is not None
    return found


def test_insert_without_a_version_stores_null_version_and_versioned_at(
    store: Store,
) -> None:
    _insert(store)
    stored = _stored(store)
    assert stored.version is None
    assert stored.versioned_at is None
    assert stored.reported_at == at(1)
    assert stored.changed == "first text"


def test_insert_with_a_version_stores_both(store: Store) -> None:
    _insert(store, version="tag-one")
    stored = _stored(store)
    assert stored.version == "tag-one"
    assert stored.versioned_at == at(1)
    assert stored.reported_at == at(1)


def test_touched_round_trips_as_a_tuple_in_order(store: Store) -> None:
    with store.write() as transaction:
        releases.insert_release(
            transaction, PROVIDER, FULL_HASH, None, "text", ("z", "a", "m"), at(1)
        )
    assert _stored(store).touched == ("z", "a", "m")


def test_add_version_sets_the_version_and_replaces_the_text(store: Store) -> None:
    _insert(store)
    before = _stored(store)
    with store.write() as transaction:
        releases.add_version(
            transaction, PROVIDER, FULL_HASH, "tag-one", "release text", ("db",), at(5)
        )
    after = _stored(store)
    assert (after.version, after.versioned_at) == ("tag-one", at(5))
    assert (after.changed, after.touched) == ("release text", ("db",))
    assert (after.reported_at, after.seq) == (before.reported_at, before.seq)


def test_a_second_add_version_on_a_versioned_row_does_the_same(store: Store) -> None:
    _insert(store, version="tag-one")
    before = _stored(store)
    with store.write() as transaction:
        releases.add_version(
            transaction, PROVIDER, FULL_HASH, "tag-two", "later text", ("db",), at(9)
        )
    after = _stored(store)
    assert (after.version, after.versioned_at) == ("tag-two", at(9))
    assert after.changed == "later text"
    assert (after.reported_at, after.seq) == (before.reported_at, before.seq)


def _correct(store: Store, version: str | None, hours: int) -> Release:
    with store.write() as transaction:
        releases.correct_release(
            transaction,
            PROVIDER,
            FULL_HASH,
            version,
            "fixed text",
            ("fixed",),
            at(hours),
        )
    return _stored(store)


def test_correcting_a_versionless_row_keeps_it_versionless(store: Store) -> None:
    _insert(store)
    corrected = _correct(store, None, 4)
    assert corrected.version is None
    assert corrected.versioned_at is None
    assert corrected.reported_at == at(4)
    assert (corrected.changed, corrected.touched) == ("fixed text", ("fixed",))


def test_correcting_a_versioned_row_keeps_the_version_and_moves_versioned_at(
    store: Store,
) -> None:
    _insert(store, version="tag-one")
    corrected = _correct(store, None, 4)
    assert corrected.version == "tag-one"
    assert corrected.versioned_at == at(4)
    assert corrected.reported_at == at(4)


def test_correcting_with_a_new_version_sets_it(store: Store) -> None:
    _insert(store, version="tag-one")
    corrected = _correct(store, "tag-two", 4)
    assert (corrected.version, corrected.versioned_at) == ("tag-two", at(4))


def test_correcting_a_versionless_row_with_a_version_versions_it(store: Store) -> None:
    _insert(store)
    corrected = _correct(store, "tag-one", 4)
    assert (corrected.version, corrected.versioned_at) == ("tag-one", at(4))


def test_delete_removes_the_row_and_a_reinsert_gets_a_higher_seq(store: Store) -> None:
    _insert(store)
    first_seq = _stored(store).seq
    with store.write() as transaction:
        assert releases.delete_release(transaction, PROVIDER, FULL_HASH) is True
        assert releases.release_for_commit(transaction, PROVIDER, FULL_HASH) is None
    _insert(store, hours=2)
    assert _stored(store).seq > first_seq


def test_delete_of_an_unknown_commit_returns_false(store: Store) -> None:
    with store.write() as transaction:
        assert releases.delete_release(transaction, PROVIDER, OTHER_HASH) is False


def test_release_for_commit_is_per_member_and_per_commit(store: Store) -> None:
    _insert(store)
    with store.read() as transaction:
        assert (
            releases.release_for_commit(transaction, OTHER_PROVIDER, FULL_HASH) is None
        )
        assert releases.release_for_commit(transaction, PROVIDER, OTHER_HASH) is None
        assert releases.release_for_commit(transaction, PROVIDER, FULL_HASH) is not None


def test_a_duplicate_member_and_commit_raises_and_is_not_caught(store: Store) -> None:
    _insert(store)
    with pytest.raises(StoreIntegrityError), store.write() as transaction:
        releases.insert_release(
            transaction, PROVIDER, FULL_HASH, None, "again", TOUCHED, at(2)
        )


def test_two_members_may_report_the_same_commit(store: Store) -> None:
    _insert(store)
    with store.write() as transaction:
        releases.insert_release(
            transaction, OTHER_PROVIDER, FULL_HASH, None, "theirs", TOUCHED, at(2)
        )
        found = releases.release_for_commit(transaction, OTHER_PROVIDER, FULL_HASH)
    assert found is not None
    assert found.changed == "theirs"
