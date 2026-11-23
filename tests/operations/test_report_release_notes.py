"""``report_release`` writes release notes in its own transaction (slice 243, D5).

Which consumers get one is ``test_release_notes_match_changes``; this is the write
path: the rows, the outcomes that write none, and the atomicity with the report."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from store.message_support import delivery_rows
from store.release_support import FULL_HASH, OTHER_HASH, PROVIDER, seed_members
from store_open import open_local_store

from amoeba.operations import note_room, release_notes
from amoeba.operations import report_release as report_release_module
from amoeba.operations.deps import Deps
from amoeba.operations.release_notes import RELEASE_NOTE_ID_PREFIX
from amoeba.operations.report_release import report_release
from amoeba.operations.report_release_models import ReportOutcome, ReportReleaseResult
from amoeba.store.errors import StoreIntegrityError
from amoeba.store.models import Message
from amoeba.store.notes import NewNote
from amoeba.store.notes import insert_note as real_insert_note
from amoeba.store.store import Store, Transaction
from operations.release_support import (
    PROVIDER_DIR,
    RELEASE_CONSUMER,
    SOURCE_CONSUMER,
    SOURCE_CONSUMER_DIR,
    SettableClock,
    note_rows,
    notified,
    release_deps,
    release_rows,
    seed_pairs,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        seed_pairs(opened)
        yield opened


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def deps(tmp_path: Path, clock: SettableClock) -> Deps:
    return release_deps(tmp_path, clock)


def _call(
    store: Store,
    deps: Deps,
    mode: str = "report",
    *,
    commit: str = FULL_HASH,
    version: str | None = None,
    directory: Path = PROVIDER_DIR,
) -> ReportReleaseResult:
    document: dict[str, object] = {"mode": mode, "commit": commit}
    if mode != "withdraw":
        document.update(changed="what changed", touched=["cli"])
    if version is not None:
        document["version"] = version
    return report_release(store, document, directory=directory, deps=deps)


def test_each_note_is_a_note_row_from_the_provider_with_one_sent_delivery(
    store: Store, deps: Deps
) -> None:
    _call(store, deps, version="tag-one")

    rows = note_rows(store)
    assert sorted(row[2] for row in rows) == sorted([SOURCE_CONSUMER, RELEASE_CONSUMER])
    for message_id, from_member, _to, _subject, _body in rows:
        assert message_id.startswith(RELEASE_NOTE_ID_PREFIX)
        assert from_member == PROVIDER
    with store.read() as transaction:
        deliveries = delivery_rows(transaction)
    assert sorted((member, event) for _seq, member, _id, event in deliveries) == sorted(
        [(SOURCE_CONSUMER, "sent"), (RELEASE_CONSUMER, "sent")]
    )
    assert {message for _seq, _member, message, _event in deliveries} == {
        row[0] for row in rows
    }


def test_two_consumers_get_two_rows_with_different_ids(
    store: Store, deps: Deps
) -> None:
    _call(store, deps, version="tag-one")

    first, second = (row[0] for row in note_rows(store))
    assert first != second


def test_unchanged_and_a_rejected_correct_write_no_note(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _call(store, deps, commit=OTHER_HASH)
    written = len(note_rows(store))

    clock.now += timedelta(hours=1)
    again = _call(store, deps, commit=OTHER_HASH)
    rejected = _call(store, deps, "correct", commit=FULL_HASH)

    assert again.outcome is ReportOutcome.UNCHANGED
    assert rejected.outcome is ReportOutcome.REJECTED
    assert len(note_rows(store)) == written


def test_a_withdrawal_notes_the_consumers_that_could_see_the_report_before_the_delete(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _call(store, deps, version="tag-one")
    clock.now += timedelta(hours=1)

    result = _call(store, deps, "withdraw")

    assert result.outcome is ReportOutcome.WITHDRAWN
    assert release_rows(store) == []
    withdrawn = [
        row for row in note_rows(store) if row[3].startswith("Release report withdrawn")
    ]
    assert sorted(row[2] for row in withdrawn) == sorted(
        [SOURCE_CONSUMER, RELEASE_CONSUMER]
    )


def test_a_provider_with_no_consumers_stores_its_report_and_no_note(
    store: Store, deps: Deps
) -> None:
    _call(store, deps, directory=SOURCE_CONSUMER_DIR)

    assert len(release_rows(store)) == 1
    assert note_rows(store) == []


# --- atomicity -------------------------------------------------------------


def _failing_on_second(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def insert_note(
        transaction: Transaction,
        note: NewNote,
        recipient_ids: Sequence[str],
        now: datetime,
    ) -> Message:
        calls.append("call")
        if len(calls) == 2:
            raise StoreIntegrityError("the second note failed")
        return real_insert_note(transaction, note, recipient_ids, now)

    monkeypatch.setattr(release_notes, "insert_note", insert_note)


def test_a_failing_note_write_rolls_back_the_report_and_the_notes_and_a_retry_works(
    store: Store, deps: Deps, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as patched:
        _failing_on_second(patched)
        with pytest.raises(StoreIntegrityError, match="second note"):
            _call(store, deps, version="tag-one")

    assert release_rows(store) == []
    assert note_rows(store) == []
    with store.read() as transaction:
        assert delivery_rows(transaction) == []

    retried = _call(store, deps, version="tag-one")

    assert retried.outcome is ReportOutcome.RECORDED
    assert len(release_rows(store)) == 1
    assert sorted(notified(store)) == sorted([SOURCE_CONSUMER, RELEASE_CONSUMER])


def test_a_report_missing_after_its_write_fails_loudly_instead_of_skipping_its_notes(
    store: Store, deps: Deps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The invariant the notes rest on: a written report can be read back. If it
    cannot, the call raises and rolls back, never stores a report with no notes."""
    monkeypatch.setattr(report_release_module.releases, "release_for_commit", _none)

    with pytest.raises(ValueError, match="stored report"):
        _call(store, deps, version="tag-one")

    assert release_rows(store) == []
    assert note_rows(store) == []


def _none(*_arguments: object) -> None:
    return None


def test_a_provider_at_the_note_cap_drops_its_oldest_release_notes(
    store: Store, deps: Deps, clock: SettableClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(note_room, "MAX_NOTES_PER_SENDER", 2)
    _call(store, deps, version="tag-one")
    first = {row[0] for row in note_rows(store)}
    clock.now += timedelta(hours=1)

    _call(store, deps, commit=OTHER_HASH, version="tag-two")

    rows = note_rows(store)
    assert len(rows) == 2
    assert {row[0] for row in rows} != first
