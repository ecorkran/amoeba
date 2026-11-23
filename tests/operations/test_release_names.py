"""``changes`` and ``report_release`` find the caller and the names in the store, with
a ``cf`` that answers only the caller's directory (slice 261, D5, D6)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from store.release_support import FULL_HASH, OTHER_PROVIDER, PROVIDER, at, seed_members
from store_open import open_local_store

from amoeba.operations.changes_models import ChangesOutcome
from amoeba.operations.report_release_models import ReportOutcome
from amoeba.store.member_names import set_member_name
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from operations.release_placed import changes, report_release
from operations.release_support import (
    PROVIDER_DIR,
    SOURCE_CONSUMER,
    SOURCE_CONSUMER_DIR,
    SettableClock,
    note_rows,
    release_cf,
    release_deps,
    seed_pairs,
)

NAMES = {
    PROVIDER: "provider",
    OTHER_PROVIDER: "other-provider",
    SOURCE_CONSUMER: "source-consumer",
}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        seed_pairs(opened)
        with opened.write() as transaction:
            for member_id, name in NAMES.items():
                set_member_name(transaction, member_id, name, at(0))
        yield opened


def test_changes_names_the_caller_and_its_providers_from_the_store(
    store: Store, tmp_path: Path
) -> None:
    cf = release_cf()
    deps = release_deps(tmp_path, SettableClock(), cf=cf)

    result = changes(
        store,
        {"since": encode_timestamp(at(0))},
        directory=SOURCE_CONSUMER_DIR,
        deps=deps,
    )

    assert result.outcome is ChangesOutcome.LISTED
    assert result.member is not None
    assert (result.member.id, result.member.name) == (
        SOURCE_CONSUMER,
        "source-consumer",
    )
    assert [(pair.provider.id, pair.provider.name) for pair in result.pairs] == [
        (PROVIDER, "provider")
    ]
    assert len(cf.calls) == 1


def test_report_release_finds_the_caller_and_notes_its_consumers(
    store: Store, tmp_path: Path
) -> None:
    cf = release_cf()
    deps = release_deps(tmp_path, SettableClock(), cf=cf)

    result = report_release(
        store,
        {"commit": FULL_HASH, "changed": "a change", "touched": ["api"]},
        directory=PROVIDER_DIR,
        deps=deps,
    )

    assert result.outcome is ReportOutcome.RECORDED
    assert result.member == PROVIDER
    # A report goes to the consumers that read from source (243 D2).
    assert [row[2] for row in note_rows(store)] == [SOURCE_CONSUMER]
    assert len(cf.calls) == 1
