"""``report_release`` under concurrent writers (slice 227, D2).

``BEGIN IMMEDIATE`` serializes writers and the stored-row check shares the
transaction. Eight writers, each with its own connection as separate processes would
have, report at once: the same commit is recorded once, distinct commits are all kept,
and under a realistic burst no write waits out the store's busy timeout and the whole
burst finishes within a throughput budget.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from operations.release_support import (
    PROVIDER_DIR,
    SettableClock,
    release_deps,
    release_rows,
)
from store.release_support import FULL_HASH, PROVIDER, seed_members

from amoeba.operations.report_release import report_release
from amoeba.operations.report_release_models import ReportOutcome
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store

WRITERS = 8
REPORTS_PER_WRITER = 25
#: A write that took this long waited out the store's busy timeout (and would have
#: raised): serialized writes of this size take milliseconds.
LATENCY_BOUND_SECONDS = BUSY_TIMEOUT_SECONDS
#: The whole burst of ``WRITERS * REPORTS_PER_WRITER`` writes, with generous headroom
#: for a slow runner; a burst this slow is lock contention that has gone wrong.
BURST_BUDGET_SECONDS = 30.0


@dataclass(frozen=True)
class Burst:
    outcomes: list[ReportOutcome]
    slowest_write_seconds: float
    elapsed_seconds: float


def _document(commit: str, changed: str) -> dict[str, object]:
    return {"commit": commit, "changed": changed, "touched": ["api"]}


def _burst(tmp_path: Path, batches: list[list[dict[str, object]]]) -> Burst:
    """Each batch is one writer's documents, run in order on its own connection; all
    writers start together."""
    path = tmp_path / "amoeba.sqlite3"
    with Store.open(path) as setup:
        seed_members(setup)
    deps = release_deps(tmp_path, SettableClock())
    gate = threading.Barrier(len(batches))

    def write_all(batch: list[dict[str, object]]) -> list[tuple[ReportOutcome, float]]:
        results: list[tuple[ReportOutcome, float]] = []
        with Store.open(path) as store:
            gate.wait(timeout=LATENCY_BOUND_SECONDS)
            for document in batch:
                started = time.monotonic()
                outcome = report_release(
                    store, document, directory=PROVIDER_DIR, deps=deps
                ).outcome
                results.append((outcome, time.monotonic() - started))
        return results

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(batches)) as pool:
        per_writer = list(pool.map(write_all, batches))
    elapsed = time.monotonic() - started
    results = [result for writer in per_writer for result in writer]
    return Burst(
        outcomes=[outcome for outcome, _ in results],
        slowest_write_seconds=max(seconds for _, seconds in results),
        elapsed_seconds=elapsed,
    )


def test_the_same_commit_reported_by_eight_writers_is_recorded_once(
    tmp_path: Path,
) -> None:
    batches = [[_document(FULL_HASH, f"writer {number}")] for number in range(WRITERS)]

    burst = _burst(tmp_path, batches)

    assert burst.outcomes.count(ReportOutcome.RECORDED) == 1
    assert burst.outcomes.count(ReportOutcome.UNCHANGED) == WRITERS - 1
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        (row,) = release_rows(store)
    assert row[1] == PROVIDER


def test_a_burst_of_distinct_reports_is_kept_within_the_latency_and_budget(
    tmp_path: Path,
) -> None:
    batches = [
        [
            _document(
                f"{writer * REPORTS_PER_WRITER + report:040x}", f"report {report}"
            )
            for report in range(REPORTS_PER_WRITER)
        ]
        for writer in range(WRITERS)
    ]

    burst = _burst(tmp_path, batches)

    total = WRITERS * REPORTS_PER_WRITER
    assert burst.outcomes == [ReportOutcome.RECORDED] * total
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        rows = release_rows(store)
    assert len(rows) == total
    assert len({row[0] for row in rows}) == total, "every row has its own seq"
    assert burst.slowest_write_seconds < LATENCY_BOUND_SECONDS
    assert burst.elapsed_seconds < BURST_BUDGET_SECONDS
