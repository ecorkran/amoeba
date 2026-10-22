"""Recovery at scale, and the assertions that actually guard the algorithm.

Since slice 120 an ``sq_run`` entry carries its run id, so recovery has two
paths and each has an exact bound:

* **By id**: one ``sq runs wait`` poll per entry and *zero* run-state file
  reads. A scan here would mean recovery is back to reading Squadron's
  internals.
* **Legacy** (rows journaled before 120): exactly one directory scan per pass,
  however many entries, and only when a legacy entry exists. Per-entry scans
  are the O(n·m) mistake a timing bound on a fast machine would let through.

The exact counts are what do the real work; the timing bounds are backstops.
Run files here are synthesized: this tier measures scale, and real-fixture
coverage is ``tests/test_observer_sq_runs.py``'s job.

Measured 20260921 on the development machine (Darwin 25.5.0, Python 3.13.7,
SQLite 3.50.4), legacy matching, before slice 120:

    500 unresolved entries against 1000 run files    0.170 s
    recovery growth, 100 -> 200 entries              0.022 s -> 0.031 s (1.4x)
    bound asserted                                   30    s

The LLD's candidate was "500 entries against 1000 files under 30 s". The
measurement came in roughly 175x under that candidate, and the candidate is
kept as the asserted bound rather than tightened: a ~0.4 s bound would be
dominated by machine variance, and the failure this tier exists to catch costs
about 500x, not 2x. Measured values are printed on every run.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from load_harness import PROJECT, seed_project, synthesize_runs
from sq_run_fixtures import insert_legacy_sq_run_entry, sq_run_parameters

import amoeba.process.observers.sq_run_id as sq_run_id
from amoeba.process.observers import sq_runs
from amoeba.process.observers.sq_run_id import SquadronRunIdObserver
from amoeba.process.recovery import NotApplied, RecoverySummary, reconcile
from amoeba.process.settings import ProcessSettings
from amoeba.process.sq_outcome import PollFailure, RunOutcome, RunOutcomeDocument
from amoeba.process.supervisor import build_observer_registry
from amoeba.store import CommandKind, JournalEntry, Store

#: The scale the LLD names.
ENTRY_COUNT = 500
RUN_FILE_COUNT = 1000

#: Asserted bound on total recovery time. See the module docstring.
RECOVERY_BOUND_SECONDS = 30.0

#: Exactly one directory scan per recovery pass that has a legacy entry.
EXPECTED_SCANS_PER_LEGACY_PASS = 1

#: Start-up bound (D4): sleeps add up to at most one grace; two polls per entry.
STARTUP_GRACE_SECONDS = 60.0
STARTUP_ENTRY_COUNT = 50
MAX_POLLS_PER_ENTRY = 2


def _issue_id_entries(store: Store, node_id: str, count: int) -> list[str]:
    """Journal ``count`` unresolved ``sq_run`` entries that carry a run id."""
    return [
        store.journal_issue(
            node_id,
            kind=CommandKind.SQ_RUN,
            parameters=sq_run_parameters(
                {"pipeline": "loadtest", "params": {"index": str(index)}},
                run_id=f"run-load-{index}",
            ),
        ).id
        for index in range(count)
    ]


def _issue_legacy_entries(
    store: Store, project_id: str, node_id: str, count: int
) -> list[str]:
    """Write ``count`` unresolved pre-120 rows (no run id), as the store once did."""
    issued_at = datetime.now(UTC).isoformat()
    ids = [f"legacy-{index}" for index in range(count)]
    with closing(sqlite3.connect(store.path)) as connection:
        for index, entry_id in enumerate(ids):
            insert_legacy_sq_run_entry(
                connection,
                entry_id=entry_id,
                project_id=project_id,
                node_id=node_id,
                parameters={"pipeline": "loadtest", "params": {"index": str(index)}},
                issued_at=issued_at,
            )
    return ids


class PollCounter:
    """Stands in for ``poll_run``: a completed run for every id, and a count."""

    def __init__(self) -> None:
        self.run_ids: list[str] = []

    def __call__(
        self, run_id: str, *, timeout_seconds: float
    ) -> RunOutcomeDocument | PollFailure:
        self.run_ids.append(run_id)
        return RunOutcomeDocument(
            run_id=run_id, outcome=RunOutcome.COMPLETED, status="completed"
        )


class ScanCounter:
    """Wraps the real scan so a test can count how often the directory is read."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls: list[Path] = []
        self._real = sq_runs.scan_runs_directory
        # The scan originates in the observer module only: the registry no longer
        # scans eagerly, so a second patch point would hide a regression.
        monkeypatch.setattr(sq_runs, "scan_runs_directory", self)

    def __call__(self, directory: Path) -> sq_runs.RunsDirectoryScan:
        self.calls.append(directory)
        return self._real(directory)


def test_a_pass_of_id_bearing_entries_polls_once_each_and_scans_nothing(
    supervisor_dir: Path, runs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """By id: ``ENTRY_COUNT`` polls, one per entry, and zero directory scans."""
    store_file = seed_project(supervisor_dir)
    synthesize_runs(runs_dir, 50)
    scans = ScanCounter(monkeypatch)
    polls = PollCounter()
    monkeypatch.setattr(sq_run_id, "poll_run", polls)
    settings = ProcessSettings(sq_runs_dir=runs_dir)

    with Store.open(store_file) as store:
        node = store.nodes_for_project(PROJECT)[0]
        _issue_id_entries(store, node.id, ENTRY_COUNT)
        registry = build_observer_registry(
            settings, store.recorded_result_run_ids(PROJECT)
        )
        summary = reconcile(store, PROJECT, registry)

    assert scans.calls == [], f"id-bearing recovery scanned {scans.calls}"
    assert len(polls.run_ids) == ENTRY_COUNT
    assert len(set(polls.run_ids)) == ENTRY_COUNT
    assert summary.adopted == ENTRY_COUNT


def test_a_pass_with_legacy_entries_scans_the_runs_directory_exactly_once(
    supervisor_dir: Path, runs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy: one scan per pass, not one per entry, however many entries.

    The count is exact and compared across two entry counts: a per-entry scan is
    only visible as a regression when 10 entries and 500 entries differ.
    """
    synthesize_runs(runs_dir, 20)
    settings = ProcessSettings(sq_runs_dir=runs_dir)

    counts: dict[int, int] = {}
    for entry_count in (10, ENTRY_COUNT):
        project_id = f"scan{entry_count}"
        store_file = seed_project(supervisor_dir, project_id)
        scans = ScanCounter(monkeypatch)

        with Store.open(store_file) as store:
            node = store.nodes_for_project(project_id)[0]
            _issue_legacy_entries(store, project_id, node.id, entry_count)
            registry = build_observer_registry(
                settings, store.recorded_result_run_ids(project_id)
            )
            reconcile(store, project_id, registry)

        counts[entry_count] = len(scans.calls)

    assert counts[10] == counts[ENTRY_COUNT] == EXPECTED_SCANS_PER_LEGACY_PASS, (
        f"the scan count grew with the entry count: {counts[10]} scans for 10 "
        f"entries, {counts[ENTRY_COUNT]} for {ENTRY_COUNT}. The runs directory "
        "must be read once per recovery pass, not once per entry."
    )


class FakeClock:
    """A clock that only moves when the observer sleeps, as real time would."""

    def __init__(self, start: datetime) -> None:
        self.now = start
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += timedelta(seconds=seconds)


def test_startup_stall_is_bounded_by_one_grace_and_two_polls_per_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D4: in-grace ``not_found`` entries delay start-up by at most one grace.

    Each deadline is absolute, so entries issued at different moments within the
    grace period sleep to their own deadlines in turn and the clock never runs
    past the latest one: the sleeps add up to at most ``STARTUP_GRACE_SECONDS``.
    """
    clock = FakeClock(datetime(2026, 10, 22, 12, 0, tzinfo=UTC))
    polls: list[str] = []

    def not_found(run_id: str, *, timeout_seconds: float) -> RunOutcomeDocument:
        polls.append(run_id)
        return RunOutcomeDocument(run_id=run_id, outcome=RunOutcome.NOT_FOUND)

    observer = SquadronRunIdObserver(
        launch_grace_seconds=STARTUP_GRACE_SECONDS,
        poll_timeout_seconds=10.0,
        claimed_run_ids=None,
        now=lambda: clock.now,
        sleep=clock.sleep,
    )
    entries = [
        JournalEntry(
            id=f"entry-{index}",
            project_id=PROJECT,
            node_id="node-1",
            kind=CommandKind.SQ_RUN,
            parameters=sq_run_parameters(
                {"pipeline": "p", "params": {}}, f"run-{index}"
            ),
            # Spread across the grace period, oldest first as recovery sees them.
            issued_at=clock.now - timedelta(seconds=STARTUP_GRACE_SECONDS - 1 - index),
        )
        for index in range(STARTUP_ENTRY_COUNT)
    ]
    monkeypatch.setattr(sq_run_id, "poll_run", not_found)

    observations = [observer.observe(entry) for entry in entries]

    assert all(isinstance(o, NotApplied) for o in observations)
    assert sum(clock.slept) <= STARTUP_GRACE_SECONDS
    assert len(polls) <= MAX_POLLS_PER_ENTRY * STARTUP_ENTRY_COUNT


def _timed(action: Callable[[], object]) -> float:
    started = time.monotonic()
    action()
    return time.monotonic() - started


def test_legacy_recovery_of_many_entries_against_many_run_files_stays_bounded(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """The LLD's scale case, timed: 500 legacy entries against 1000 run files."""
    store_file = seed_project(supervisor_dir)

    # Runs started before the entries are issued, so none is a candidate on
    # the clock-tolerance condition alone — every entry escalates, which is
    # the most work recovery can be asked to do per entry.
    synthesize_runs(
        runs_dir,
        RUN_FILE_COUNT,
        started_at=datetime.now(UTC) - timedelta(days=1),
    )
    settings = ProcessSettings(sq_runs_dir=runs_dir)

    with Store.open(store_file) as store:
        node = store.nodes_for_project(PROJECT)[0]
        entry_ids = _issue_legacy_entries(store, PROJECT, node.id, ENTRY_COUNT)
        registry = build_observer_registry(
            settings, store.recorded_result_run_ids(PROJECT)
        )

        summaries: list[RecoverySummary] = []
        elapsed = _timed(lambda: summaries.append(reconcile(store, PROJECT, registry)))
        unresolved = store.unresolved_journal_entries(PROJECT)

    assert elapsed < RECOVERY_BOUND_SECONDS, (
        f"recovery of {ENTRY_COUNT} entries against {RUN_FILE_COUNT} run "
        f"files took {elapsed:.3f}s, over the {RECOVERY_BOUND_SECONDS}s bound"
    )
    assert summaries[0].total == len(entry_ids)
    assert unresolved == [], "recovery must leave nothing unresolved"

    print(
        f"\nlegacy recovery of {ENTRY_COUNT} entries against {RUN_FILE_COUNT} run "
        f"files: {elapsed:.3f}s (bound {RECOVERY_BOUND_SECONDS}s)"
    )


def test_legacy_recovery_scales_without_a_quadratic_blowup(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """Doubling the entries roughly doubles the work, rather than squaring it.

    A complementary shape-check to the exact scan count: it catches an O(n²)
    match that reads the directory once but compares every entry against every
    other entry's recorded result.
    """
    synthesize_runs(runs_dir, 200, started_at=datetime.now(UTC) - timedelta(days=1))
    settings = ProcessSettings(sq_runs_dir=runs_dir)

    durations: dict[int, float] = {}
    for count in (100, 200):
        project_id = f"scale{count}"
        store_file = seed_project(supervisor_dir, project_id)

        with Store.open(store_file) as store:
            node = store.nodes_for_project(project_id)[0]
            _issue_legacy_entries(store, project_id, node.id, count)

            registry = build_observer_registry(
                settings, store.recorded_result_run_ids(project_id)
            )
            durations[count] = _timed(
                lambda s=store, p=project_id, r=registry: reconcile(s, p, r)
            )

    # Generous: quadratic growth would be ~4x, and this allows 3x before
    # failing, so ordinary variance on a loaded machine does not trip it.
    growth = durations[200] / max(durations[100], 1e-6)

    assert growth < 3.0, (
        f"doubling the entry count multiplied recovery time by {growth:.1f} "
        f"({durations[100]:.3f}s -> {durations[200]:.3f}s), which suggests "
        "the match is not linear in the number of entries"
    )

    print(
        f"\nrecovery growth 100 -> 200 entries: {durations[100]:.3f}s -> "
        f"{durations[200]:.3f}s ({growth:.1f}x)"
    )
