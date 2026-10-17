"""Load tier for slice 108: what an idle tick costs, and what one change costs.

``CFWatchTenant.tick`` runs synchronously on the resident process loop, so its
cost is every other tenant's latency. Two things are measured:

**Idle tick.** ``PROJECT_COUNT`` projects each link one CF project, in a
``projects.json`` of ``ENTRY_COUNT`` entries. Once every link has been observed,
a tick with an unchanged file must read no file at all (the exact assertion that
guards the algorithm: one ``stat`` and one link query per project). The time
bound is a backstop.

**One change.** The file is rewritten with one pointer moved. The tick reads the
file once, parses it once per link, and must record exactly one snapshot. The
bound is a backstop for the whole pass.

Measured 20261017 on the development machine (Darwin 25.5.0, Python 3.13.7):

    100 projects, 500-entry file, idle tick           0.4 ms   (bound 1 s)
    100 links, 500-entry file, one-change pass        124 ms   (bound 10 s)

The change pass parses the file once per link, so it grows with links times file
size. It happens once per real CF write, not once per interval, and the real
file is about 30 KB with a handful of links; the figure above is a deliberately
large case.

The bounds are backstops for a loaded CI machine, not targets; the zero-reads
and one-snapshot assertions do the real work. Both values are printed on every
run, so a bound that stops matching reality is visible.
"""

from __future__ import annotations

import copy
import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cf_fixture import AMOEBA_ID, DEFAULT_WORKTREE_ID, fixture_entries
from cf_watch_harness import CFRig
from local_host_harness import LocalHost

from amoeba.process.settings import ProcessSettings

PROJECT_COUNT = 100
ENTRY_COUNT = 500
IDLE_TICKS = 20
IDLE_TICK_BOUND_SECONDS = 1.0
CHANGE_TICK_BOUND_SECONDS = 10.0


@pytest.fixture
def local_host(supervisor_dir: Path) -> Iterator[LocalHost]:
    host = LocalHost(supervisor_dir, ProcessSettings())
    try:
        yield host
    finally:
        host.stores.close_all()


def _big_file() -> list[dict[str, Any]]:
    """``ENTRY_COUNT`` entries, each a copy of the real amoeba entry."""
    template = next(e for e in fixture_entries() if e["id"] == AMOEBA_ID)
    entries: list[dict[str, Any]] = []
    for index in range(ENTRY_COUNT):
        entry = copy.deepcopy(template)
        entry["id"] = f"project_{index:05}"
        entries.append(entry)
    return entries


def _linked_rig(
    local_host: LocalHost, cf_dir: Path
) -> tuple[CFRig, list[dict[str, Any]]]:
    rig = CFRig(local_host, cf_dir)
    entries = _big_file()
    rig.write(json.dumps(entries).encode("utf-8"))
    for index in range(PROJECT_COUNT):
        rig.link(f"project_{index:05}", f"load-{index:03}")
    rig.tick()  # first sighting of every link
    return rig, entries


def test_an_idle_tick_reads_no_file(
    local_host: LocalHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig, _ = _linked_rig(local_host, tmp_path)
    assert sum(len(rig.snapshots(f"load-{i:03}")) for i in range(PROJECT_COUNT)) == (
        PROJECT_COUNT
    )
    reads: list[Path] = []
    real_read = Path.read_bytes

    def counting(self: Path) -> bytes:
        reads.append(self)
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    started = time.perf_counter()
    for _ in range(IDLE_TICKS):
        assert rig.tick() is False
    per_tick = (time.perf_counter() - started) / IDLE_TICKS

    print(f"\n{PROJECT_COUNT} projects: {per_tick * 1000:.1f} ms per idle tick")
    assert reads == []
    assert per_tick < IDLE_TICK_BOUND_SECONDS


def test_one_change_costs_one_snapshot_and_a_bounded_pass(
    local_host: LocalHost, tmp_path: Path
) -> None:
    rig, entries = _linked_rig(local_host, tmp_path)
    before = sum(len(rig.snapshots(f"load-{i:03}")) for i in range(PROJECT_COUNT))
    entries[7]["worktrees"][0]["developmentPhase"] = "Phase 7: Testing"
    assert entries[7]["worktrees"][0]["id"] == DEFAULT_WORKTREE_ID
    rig.write(json.dumps(entries).encode("utf-8"))

    started = time.perf_counter()
    assert rig.tick() is True
    elapsed = time.perf_counter() - started

    after = sum(len(rig.snapshots(f"load-{i:03}")) for i in range(PROJECT_COUNT))
    print(f"\n{PROJECT_COUNT} links, one change: {elapsed * 1000:.0f} ms for the pass")
    assert after == before + 1
    assert elapsed < CHANGE_TICK_BOUND_SECONDS
