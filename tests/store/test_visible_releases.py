"""What each ``consumed`` mode sees of a provider's reports (slice 227, D3)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.store import releases
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode
from store.release_support import (
    FULL_HASH,
    OTHER_HASH,
    OTHER_PROVIDER,
    PROVIDER,
    THIRD_HASH,
    at,
    seed_members,
)

TOUCHED = ("api",)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _report(
    store: Store, commit: str, hours: int, *, version: str | None = None
) -> None:
    with store.write() as transaction:
        releases.insert_release(
            transaction,
            PROVIDER,
            commit,
            version,
            f"text {commit[:1]}",
            TOUCHED,
            at(hours),
        )


def _seen(
    store: Store, consumed: ConsumedMode, since_hours: int, provider: str = PROVIDER
) -> tuple[str, ...]:
    with store.read() as transaction:
        found = releases.visible_releases(
            transaction, provider, consumed, encode_timestamp(at(since_hours))
        )
    return tuple(release.commit for release in found)


def test_a_versionless_report_reaches_from_source_only(store: Store) -> None:
    _report(store, FULL_HASH, 1)
    assert _seen(store, ConsumedMode.FROM_SOURCE, 0) == (FULL_HASH,)
    assert _seen(store, ConsumedMode.FROM_RELEASE, 0) == ()


def test_after_versioning_from_release_sees_it_with_the_release_text(
    store: Store,
) -> None:
    _report(store, FULL_HASH, 1)
    with store.write() as transaction:
        releases.add_version(
            transaction, PROVIDER, FULL_HASH, "tag-one", "release text", TOUCHED, at(5)
        )
    with store.read() as transaction:
        (seen,) = releases.visible_releases(
            transaction, PROVIDER, ConsumedMode.FROM_RELEASE, encode_timestamp(at(0))
        )
    assert (seen.version, seen.changed) == ("tag-one", "release text")


def test_from_source_since_between_report_and_tag_sees_nothing(store: Store) -> None:
    _report(store, FULL_HASH, 1)
    with store.write() as transaction:
        releases.add_version(
            transaction, PROVIDER, FULL_HASH, "tag-one", "release text", TOUCHED, at(5)
        )
    assert _seen(store, ConsumedMode.FROM_SOURCE, 3) == ()
    with store.read() as transaction:
        (seen,) = releases.visible_releases(
            transaction, PROVIDER, ConsumedMode.FROM_SOURCE, encode_timestamp(at(0))
        )
    assert seen.version == "tag-one"


def test_a_correction_is_seen_by_a_since_before_it_and_not_after(store: Store) -> None:
    _report(store, FULL_HASH, 1)
    with store.write() as transaction:
        releases.correct_release(
            transaction, PROVIDER, FULL_HASH, None, "fixed", TOUCHED, at(6)
        )
    assert _seen(store, ConsumedMode.FROM_SOURCE, 3) == (FULL_HASH,)
    assert _seen(store, ConsumedMode.FROM_SOURCE, 7) == ()


def test_from_release_sees_a_correction_only_once_the_row_is_versioned(
    store: Store,
) -> None:
    _report(store, FULL_HASH, 1)
    with store.write() as transaction:
        releases.correct_release(
            transaction, PROVIDER, FULL_HASH, None, "fixed", TOUCHED, at(6)
        )
    assert _seen(store, ConsumedMode.FROM_RELEASE, 0) == ()
    with store.write() as transaction:
        releases.add_version(
            transaction, PROVIDER, FULL_HASH, "tag-one", "fixed", TOUCHED, at(8)
        )
    assert _seen(store, ConsumedMode.FROM_RELEASE, 7) == (FULL_HASH,)


def test_a_correction_of_a_versioned_row_is_seen_again_by_from_release(
    store: Store,
) -> None:
    _report(store, FULL_HASH, 1, version="tag-one")
    with store.write() as transaction:
        releases.correct_release(
            transaction, PROVIDER, FULL_HASH, None, "fixed", TOUCHED, at(6)
        )
    assert _seen(store, ConsumedMode.FROM_RELEASE, 3) == (FULL_HASH,)
    assert _seen(store, ConsumedMode.FROM_RELEASE, 7) == ()


def test_each_mode_orders_by_its_own_time_then_seq(store: Store) -> None:
    # Seeded out of order: seq 1 reported last, seq 3 reported first.
    _report(store, FULL_HASH, 5, version="v1")
    _report(store, OTHER_HASH, 2, version="v2")
    _report(store, THIRD_HASH, 2, version="v3")
    assert _seen(store, ConsumedMode.FROM_SOURCE, 0) == (
        OTHER_HASH,
        THIRD_HASH,
        FULL_HASH,
    )
    assert _seen(store, ConsumedMode.FROM_RELEASE, 0) == (
        OTHER_HASH,
        THIRD_HASH,
        FULL_HASH,
    )


def test_from_release_orders_by_versioned_at_not_reported_at(store: Store) -> None:
    _report(store, FULL_HASH, 1)
    _report(store, OTHER_HASH, 2)
    with store.write() as transaction:
        releases.add_version(
            transaction, PROVIDER, OTHER_HASH, "v1", "t", TOUCHED, at(3)
        )
        releases.add_version(
            transaction, PROVIDER, FULL_HASH, "v2", "t", TOUCHED, at(4)
        )
    assert _seen(store, ConsumedMode.FROM_RELEASE, 0) == (OTHER_HASH, FULL_HASH)


def test_another_providers_reports_never_appear(store: Store) -> None:
    _report(store, FULL_HASH, 1)
    with store.write() as transaction:
        releases.insert_release(
            transaction, OTHER_PROVIDER, OTHER_HASH, "v1", "theirs", TOUCHED, at(1)
        )
    assert _seen(store, ConsumedMode.FROM_SOURCE, 0) == (FULL_HASH,)
    assert _seen(store, ConsumedMode.FROM_RELEASE, 0, OTHER_PROVIDER) == (OTHER_HASH,)
