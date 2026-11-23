"""A consumer gets a release note exactly when ``changes`` shows it the report
(slice 243, D5, the matrix).

Every row of D5's table is run through the real ``report_release``, then the real
``changes`` for each consumer. The oracle is ``changes``, never the SQL the recipient
rule calls: ``since`` is the event's own ``now``, the value the rule uses, and for a
withdrawal ``changes`` is asked before the report goes, with the report's own
``reported_at``. The clock advances between events on one report (D5's assumption)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pytest
from store.release_support import FULL_HASH, OTHER_PROVIDER, PROVIDER, seed_members
from store_open import open_local_store

from amoeba.operations.deps import Deps
from amoeba.operations.report_release_models import ReportOutcome
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from operations.release_placed import changes, report_release
from operations.release_support import (
    GONE_PROVIDER,
    PROVIDER_DIR,
    RELEASE_CONSUMER,
    RELEASE_CONSUMER_DIR,
    SOURCE_CONSUMER,
    SOURCE_CONSUMER_DIR,
    SettableClock,
    note_rows,
    release_deps,
    seed_pairs,
)

NAMES = {
    PROVIDER: "provider",
    OTHER_PROVIDER: "other-provider",
    SOURCE_CONSUMER: "source-consumer",
    RELEASE_CONSUMER: "release-consumer",
    GONE_PROVIDER: "gone-provider",
}
CONSUMER_DIRS = {
    SOURCE_CONSUMER: SOURCE_CONSUMER_DIR,
    RELEASE_CONSUMER: RELEASE_CONSUMER_DIR,
}
STEP = timedelta(hours=1)


@dataclass(frozen=True)
class Event:
    """One ``report_release`` call: its mode, whether it gives a version, and the
    outcome D5's table names for it."""

    mode: str
    version: str | None
    outcome: ReportOutcome


RECORD = Event("report", None, ReportOutcome.RECORDED)
RECORD_VERSIONED = Event("report", "tag-one", ReportOutcome.RECORDED)
VERSION = Event("report", "tag-one", ReportOutcome.VERSIONED)
CORRECT_KEEPING = Event("correct", None, ReportOutcome.CORRECTED)
CORRECT_ADDING = Event("correct", "tag-two", ReportOutcome.CORRECTED)
WITHDRAW = Event("withdraw", None, ReportOutcome.WITHDRAWN)

#: Each row of D5's table, as the events that lead to it; the last one is the row, and
#: every earlier event is checked too.
SCENARIOS = {
    "recorded, no version": (RECORD,),
    "recorded, with a version": (RECORD_VERSIONED,),
    "versioned": (RECORD, VERSION),
    "corrected, version kept after the write": (RECORD_VERSIONED, CORRECT_KEEPING),
    "corrected, no version after the write": (RECORD, CORRECT_KEEPING),
    "corrected, version added by the correction": (RECORD, CORRECT_ADDING),
    "withdrawn, versioned report": (RECORD_VERSIONED, WITHDRAW),
    "withdrawn, never versioned": (RECORD, WITHDRAW),
    "withdrawn after a version was added": (RECORD, VERSION, WITHDRAW),
    "withdrawn after a correction": (RECORD, CORRECT_KEEPING, WITHDRAW),
}


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


def _document(event: Event) -> dict[str, object]:
    document: dict[str, object] = {"mode": event.mode, "commit": FULL_HASH}
    if event.mode != "withdraw":
        document.update(changed="what changed", touched=["api"])
    if event.version is not None:
        document["version"] = event.version
    return document


def _consumers_seeing(store: Store, deps: Deps, since: str) -> set[str]:
    """The consumers whose ``changes`` lists the report, asked as ``since``."""
    seeing: set[str] = set()
    for consumer, directory in CONSUMER_DIRS.items():
        result = changes(store, {"since": since}, directory=directory, deps=deps)
        for pair in result.pairs:
            if pair.provider.id == PROVIDER and any(
                report.commit == FULL_HASH for report in pair.releases
            ):
                seeing.add(consumer)
    return seeing


def _stored_reported_at(store: Store, deps: Deps) -> str:
    result = changes(
        store,
        {"since": encode_timestamp(deps.clock() - timedelta(days=365))},
        directory=SOURCE_CONSUMER_DIR,
        deps=deps,
    )
    (report,) = (
        report
        for pair in result.pairs
        if pair.provider.id == PROVIDER
        for report in pair.releases
        if report.commit == FULL_HASH
    )
    return report.reported_at


@pytest.mark.parametrize("scenario", SCENARIOS, ids=list(SCENARIOS))
def test_the_consumers_with_a_note_are_exactly_those_whose_changes_lists_the_report(
    store: Store, deps: Deps, clock: SettableClock, scenario: str
) -> None:
    for event in SCENARIOS[scenario]:
        clock.now += STEP
        before = len(note_rows(store))
        # A withdrawal deletes the report, so ``changes`` is asked first, from the
        # report's own ``reported_at``; every other event is asked as ``now``.
        since = (
            _stored_reported_at(store, deps)
            if event.mode == "withdraw"
            else encode_timestamp(clock.now)
        )
        seen_before = _consumers_seeing(store, deps, since)

        result = report_release(
            store, _document(event), directory=PROVIDER_DIR, deps=deps
        )

        assert result.outcome is event.outcome
        notified = {row[2] for row in note_rows(store)[before:]}
        expected = (
            seen_before
            if event.mode == "withdraw"
            else _consumers_seeing(store, deps, since)
        )
        assert notified == expected, (scenario, event)
        assert len(note_rows(store)) - before == len(expected)
