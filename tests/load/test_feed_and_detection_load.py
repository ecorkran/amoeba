"""Load tier for slice 106: steady-state scan cost, and follower latency.

**Scan cost.** A baselined directory of ``FILE_COUNT`` reviews is scanned
repeatedly. Once every file has settled and been delivered, a scan must read
no file at all — that exact assertion is what guards the algorithm (review
finding F001: every settled file used to be re-read and re-hashed each scan).
The time bound is a backstop.

**Follower latency.** A writer commits ``BURST`` nodes as fast as it can while
a follower with the production ``FeedSettings`` tails the feed. Every change
must arrive, in order, with no gap, and the worst commit-to-arrival delay must
stay under the bound. The contract promises ``follow_interval_seconds`` plus
the read time; the bound leaves room for a loaded machine.

Measured 20261015 on the development machine (Darwin 25.5.0, Python 3.13.7):

    500 settled files, one steady scan              4.5 ms   (bound 2 s)
    1000-commit burst, worst commit-to-arrival     257 ms    (bound 2 s)

The bounds are backstops for a loaded CI machine, not targets; the exact
zero-reads assertion and the no-gap assertion do the real work. Both values are
printed on every run, so a bound that stops matching reality is visible.
"""

from __future__ import annotations

import shutil
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from detection_harness import FIXTURES, ROUND_ONE_PART_ONE, DetectionRig
from local_host_harness import LocalHost

from amoeba.feed import FeedSettings, follow
from amoeba.process.settings import ProcessSettings
from amoeba.store import Change, NodeKind, Store
from amoeba.store.paths import project_store_path

FILE_COUNT = 500
STEADY_SCANS = 10
STEADY_SCAN_BOUND_SECONDS = 2.0

BURST = 1000
PROJECT = "load"
LATENCY_BOUND_SECONDS = 2.0


@pytest.fixture
def local_host(supervisor_dir: Path) -> Iterator[LocalHost]:
    host = LocalHost(supervisor_dir, ProcessSettings())
    try:
        yield host
    finally:
        host.stores.close_all()


def test_a_steady_scan_reads_no_file(
    local_host: LocalHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    for index in range(FILE_COUNT):
        shutil.copy(FIXTURES / ROUND_ONE_PART_ONE, reviews / f"r-{index:04}.md")
    rig = DetectionRig(local_host, reviews)
    rig.watch()
    rig.run_scans(3)  # baseline, first sighting, settled delivery

    reads: list[Path] = []
    real_read = Path.read_bytes

    def counting(self: Path) -> bytes:
        reads.append(self)
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    started = time.perf_counter()
    rig.run_scans(STEADY_SCANS)
    per_scan = (time.perf_counter() - started) / STEADY_SCANS

    print(f"\n{FILE_COUNT} settled files: {per_scan * 1000:.1f} ms per steady scan")
    assert reads == []
    assert per_scan < STEADY_SCAN_BOUND_SECONDS


def test_a_follower_keeps_up_with_a_writer_burst(supervisor_dir: Path) -> None:
    path = project_store_path(supervisor_dir, PROJECT)
    committed: dict[str, float] = {}
    arrived: dict[str, float] = {}
    seen: list[Change] = []
    done = threading.Event()

    with Store.open(path) as writer:

        def consume() -> None:
            for change in follow(
                supervisor_dir,
                PROJECT,
                after=0,
                settings=FeedSettings(),
                stop=lambda: len(seen) >= BURST or done.is_set(),
            ):
                arrived[change.subject_id] = time.monotonic()
                seen.append(change)

        thread = threading.Thread(target=consume)
        thread.start()
        try:
            for _ in range(BURST):
                node = writer.create_node(
                    project_id=PROJECT, kind=NodeKind.SLICE, title="burst"
                )
                committed[node.id] = time.monotonic()
            thread.join(timeout=60)
        finally:
            done.set()
            thread.join(timeout=10)

    worst = max(arrived[node_id] - committed[node_id] for node_id in committed)
    print(f"\n{BURST} commits: worst commit-to-arrival {worst * 1000:.0f} ms")
    assert [change.seq for change in seen] == list(range(1, BURST + 1))
    assert worst < LATENCY_BOUND_SECONDS
