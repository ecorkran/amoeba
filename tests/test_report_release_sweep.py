"""``report-release`` sweeps before its own transaction, so a store that only sees
``inbox`` and ``report-release`` still prunes its notes (slice 243, D6).

Through ``wiring.invoke``, the one place both doors run the operation: the sweep is its
wiring's, not ``report_release``'s."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from operations.release_support import (
    PROVIDER_DIR,
    SOURCE_CONSUMER,
    SettableClock,
    note_rows,
    release_deps,
    release_rows,
    seed_pairs,
)
from store.release_support import FULL_HASH, PROVIDER, START, seed_members
from user_configs import example_config_text

from amoeba import wiring, wiring_releases
from amoeba.config.home import StateLayout, config_path, state_layout
from amoeba.operations.deps import Deps
from amoeba.operations.names import Door, OperationName
from amoeba.operations.report_release_models import ReportOutcome, ReportReleaseResult
from amoeba.store.errors import StoreIntegrityError
from amoeba.store.notes import NewNote, insert_note
from amoeba.store.store import Store

AGED_ID = "aged-note"
YOUNG_ID = "young-note"


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def seeded(
    tmp_path: Path, clock: SettableClock, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Store]:
    """The state-home store seeded with members, pairs and the config file, and the
    default dependencies replaced by the release ones."""
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")
    deps = release_deps(tmp_path, clock)

    def release_dependencies(_layout: StateLayout) -> Deps:
        return deps

    monkeypatch.setattr(wiring, "default_deps", release_dependencies)
    with wiring.open_store(state_layout()) as store:
        seed_members(store)
        seed_pairs(store)
        yield store


def _prune_days() -> int:
    return wiring.load_config().prune_after_days


def _write_note(store: Store, note_id: str, when: datetime) -> None:
    note = NewNote(note_id, PROVIDER, SOURCE_CONSUMER, None, "subject", "body")
    with store.write() as transaction:
        insert_note(transaction, note, [SOURCE_CONSUMER], when)


def _report() -> ReportReleaseResult:
    result = wiring.invoke(
        OperationName.REPORT_RELEASE,
        {"commit": FULL_HASH, "changed": "text", "touched": ["one"]},
        PROVIDER_DIR,
        Door.CLI,
    )
    assert isinstance(result, ReportReleaseResult)
    return result


def _note_ids(store: Store) -> set[str]:
    return {row[0] for row in note_rows(store)}


def test_an_aged_note_and_its_deliveries_are_gone_after_a_report_release(
    seeded: Store, clock: SettableClock
) -> None:
    _write_note(seeded, AGED_ID, START - timedelta(days=_prune_days() + 1))
    _write_note(seeded, YOUNG_ID, START)

    result = _report()

    assert result.outcome is ReportOutcome.RECORDED
    assert len(release_rows(seeded)) == 1
    ids = _note_ids(seeded)
    assert AGED_ID not in ids and YOUNG_ID in ids
    with seeded.read() as transaction:
        row = transaction.execute(
            "SELECT count(*) FROM deliveries WHERE message_id = ?", (AGED_ID,)
        ).fetchone()
    assert row is not None and row[0] == 0


def test_a_held_store_problem_text_still_lets_the_report_record(
    seeded: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    def held(*_args: object) -> str | None:
        return "message sweep did not run: busy"

    monkeypatch.setattr(wiring_releases, "sweep_messages", held)

    result = _report()

    assert result.outcome is ReportOutcome.RECORDED
    assert result.sweep_problem == "message sweep did not run: busy"
    assert len(release_rows(seeded)) == 1


def test_a_store_error_from_the_sweep_leaves_no_report(
    seeded: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object) -> str | None:
        raise StoreIntegrityError("the sweep failed")

    monkeypatch.setattr(wiring_releases, "sweep_messages", broken)

    with pytest.raises(StoreIntegrityError, match="sweep failed"):
        _report()

    assert release_rows(seeded) == []


def test_the_sweep_gets_the_deps_clock(
    seeded: Store, clock: SettableClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[object] = []

    def recording(_store: Store, _config: object, now: object) -> None:
        seen.append(now)

    monkeypatch.setattr(wiring_releases, "sweep_messages", recording)

    _report()

    assert seen == [clock.now]
