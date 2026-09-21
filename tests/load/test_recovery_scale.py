"""Recovery at scale, and the assertion that actually guards the algorithm.

Two things are measured here. The time bound is the softer of the two: it is
set from a measurement and catches gross regressions. **The scan-count
assertion is exact**, and it is what stops the runs directory from being read
once per entry — an O(n·m) mistake that a timing bound on a fast machine would
happily let through.

Run files here are synthesized rather than copied from upstream. That is
deliberate: this tier measures scale, and the real-fixture coverage is
``tests/test_observer_sq_runs.py``'s job.

Measured 20260921 on the development machine (Darwin 25.5.0, Python 3.13.7,
SQLite 3.50.4):

    500 unresolved entries against 1000 run files    0.170 s
    recovery growth, 100 -> 200 entries              0.022 s -> 0.031 s (1.4x)
    bound asserted                                   30    s

The LLD's candidate was "500 entries against 1000 files under 30 s". The
measurement came in roughly 175x under that candidate — far enough below it to
be worth stating plainly rather than rounding past. As with the crash loop,
**the candidate is kept as the asserted bound rather than tightened to roughly
twice the observation**, which is the deviation from the LLD's rule and is
recorded here rather than applied silently. A ~0.4 s bound would be dominated
by machine variance while adding nothing: the failure this test exists to catch
is a per-entry rescan, which at these sizes costs about 500x, not 2x.

The exact scan-count assertion is what does the real work; the timing bound is
a backstop. Both measured values are printed on every run, so a bound that
stops matching reality is visible.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from load_harness import PROJECT, seed_project, synthesize_runs

from amoeba.process.observers import sq_runs
from amoeba.process.recovery import reconcile
from amoeba.process.settings import ProcessSettings
from amoeba.process.supervisor import build_observer_registry
from amoeba.store import CommandKind, Store

#: The scale the LLD names.
ENTRY_COUNT = 500
RUN_FILE_COUNT = 1000

#: Asserted bound on total recovery time. See the module docstring.
RECOVERY_BOUND_SECONDS = 30.0

#: Exactly one directory scan per recovery pass, regardless of entry count.
#: This is the assertion that guards the algorithm.
EXPECTED_SCANS_PER_PASS = 1


def _issue_entries(store: Store, node_id: str, count: int) -> list[str]:
    """Journal ``count`` unresolved ``sq_run`` entries."""
    return [
        store.journal_issue(
            node_id,
            kind=CommandKind.SQ_RUN,
            parameters={
                "pipeline": "loadtest",
                "params": {"index": str(index)},
            },
        ).id
        for index in range(count)
    ]


def test_the_runs_directory_is_scanned_exactly_once_per_recovery_pass(
    supervisor_dir: Path, runs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact assertion: one scan per pass, not one per entry.

    Counted by wrapping the scan function itself. With 500 entries, a
    per-entry scan would register 500 — this fails loudly rather than merely
    taking longer, which is the point: on a fast machine a timing bound alone
    would not notice.
    """
    store_file = seed_project(supervisor_dir)
    synthesize_runs(runs_dir, 50)

    scan_calls: list[Path] = []
    real_scan = sq_runs.scan_runs_directory

    def _counting_scan(directory: Path) -> sq_runs.RunsDirectoryScan:
        scan_calls.append(directory)
        return real_scan(directory)

    # Patched in **both** places a scan can originate: the registry builder,
    # which is where the single up-front scan belongs, and the observer module
    # itself, which is where a lazy per-entry scan would come from. Counting
    # only the first would report zero — rather than a failure — if the
    # up-front scan were simply dropped, which is exactly the regression this
    # test must catch.
    monkeypatch.setattr("amoeba.process.supervisor.scan_runs_directory", _counting_scan)
    monkeypatch.setattr(
        "amoeba.process.observers.sq_runs.scan_runs_directory", _counting_scan
    )

    settings = ProcessSettings(sq_runs_dir=runs_dir)

    with Store.open(store_file) as store:
        node = store.nodes_for_project(PROJECT)[0]
        _issue_entries(store, node.id, ENTRY_COUNT)

        registry = build_observer_registry(
            settings, store.recorded_result_run_ids(PROJECT)
        )
        summary = reconcile(store, PROJECT, registry)

    assert len(scan_calls) == EXPECTED_SCANS_PER_PASS, (
        f"the runs directory was scanned {len(scan_calls)} times for "
        f"{ENTRY_COUNT} entries; it must be scanned exactly "
        f"{EXPECTED_SCANS_PER_PASS} time per recovery pass"
    )
    assert summary.total == ENTRY_COUNT


def test_the_scan_count_does_not_grow_with_the_entry_count(
    supervisor_dir: Path, runs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One scan per pass whether there are 10 entries or 500.

    The companion to the exact count above, and the sharper of the two: a
    per-entry scan is only *visible* as a regression if the count is compared
    across two different entry counts. A cached-but-lazy scan passes both;
    a genuinely per-entry scan fails this one with 10 against 500.
    """
    synthesize_runs(runs_dir, 20)
    settings = ProcessSettings(sq_runs_dir=runs_dir)

    counts: dict[int, int] = {}
    for entry_count in (10, ENTRY_COUNT):
        project_id = f"scan{entry_count}"
        store_file = seed_project(supervisor_dir, project_id)

        scan_calls: list[Path] = []

        # Both the call list and the real function are bound as defaults, so
        # the closure cannot pick up a later iteration's values.
        def _counting_scan(
            directory: Path,
            _calls: list[Path] = scan_calls,
            _real: Callable[[Path], sq_runs.RunsDirectoryScan] = (
                sq_runs.scan_runs_directory
            ),
        ) -> sq_runs.RunsDirectoryScan:
            _calls.append(directory)
            return _real(directory)

        monkeypatch.setattr(
            "amoeba.process.supervisor.scan_runs_directory", _counting_scan
        )
        monkeypatch.setattr(
            "amoeba.process.observers.sq_runs.scan_runs_directory", _counting_scan
        )

        with Store.open(store_file) as store:
            node = store.nodes_for_project(project_id)[0]
            _issue_entries(store, node.id, entry_count)
            registry = build_observer_registry(
                settings, store.recorded_result_run_ids(project_id)
            )
            reconcile(store, project_id, registry)

        counts[entry_count] = len(scan_calls)

    assert counts[10] == counts[ENTRY_COUNT] == EXPECTED_SCANS_PER_PASS, (
        f"the scan count grew with the entry count: {counts[10]} scans for 10 "
        f"entries, {counts[ENTRY_COUNT]} for {ENTRY_COUNT}. The runs directory "
        "must be read once per recovery pass, not once per entry."
    )


def test_recovery_of_many_entries_against_many_run_files_stays_bounded(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """The LLD's scale case, timed: 500 entries against 1000 run files."""
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
        entry_ids = _issue_entries(store, node.id, ENTRY_COUNT)

        registry = build_observer_registry(
            settings, store.recorded_result_run_ids(PROJECT)
        )

        started = time.monotonic()
        summary = reconcile(store, PROJECT, registry)
        elapsed = time.monotonic() - started

        unresolved = store.unresolved_journal_entries(PROJECT)

    assert elapsed < RECOVERY_BOUND_SECONDS, (
        f"recovery of {ENTRY_COUNT} entries against {RUN_FILE_COUNT} run "
        f"files took {elapsed:.3f}s, over the {RECOVERY_BOUND_SECONDS}s bound"
    )
    assert summary.total == len(entry_ids)
    assert unresolved == [], "recovery must leave nothing unresolved"

    print(
        f"\nrecovery of {ENTRY_COUNT} entries against {RUN_FILE_COUNT} run "
        f"files: {elapsed:.3f}s (bound {RECOVERY_BOUND_SECONDS}s)"
    )


def test_recovery_scales_without_a_quadratic_blowup(
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
            _issue_entries(store, node.id, count)

            registry = build_observer_registry(
                settings, store.recorded_result_run_ids(project_id)
            )
            started = time.monotonic()
            reconcile(store, project_id, registry)
            durations[count] = time.monotonic() - started

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
