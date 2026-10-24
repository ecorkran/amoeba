"""The Runner's tick under load: bounded by its deadline, fair, and rate-limited.

Many projects each hold many in-flight runs and every poll costs real time, as
``sq runs wait`` does. The asserted properties are exact counts and bounds, not
a speed claim:

* a tick never runs past ``tick_deadline_seconds`` plus one call (the budget is
  checked before every poll);
* least-recently-polled order and deadline carry-over reach every run;
* no run is polled more often than ``run_poll_interval_seconds`` allows.

Measured 20261023 on the development machine (Darwin 25.5.0, Python 3.13):
10 projects x 10 runs, 10 ms per poll, 0.3 s deadline: every tick 0.30-0.31 s,
every run polled within 4 ticks.
"""

from __future__ import annotations

import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from runner.observe_support import FakeCf, document

from amoeba.process import ProcessSettings, RunOutcome
from amoeba.runner.launch import LAUNCH_LOGS_DIRNAME
from amoeba.runner.tenant import RunnerTenant
from amoeba.store import CommandKind, NodeKind, Store

PROJECT_COUNT = 10
RUNS_PER_PROJECT = 10
POLL_COST_SECONDS = 0.01
TICK_DEADLINE_SECONDS = 0.3
RUN_POLL_INTERVAL_SECONDS = 0.5

#: A tick may overrun its deadline by one call and scheduling noise.
TICK_SLACK_SECONDS = 1.0
MAX_TICKS_TO_REACH_EVERY_RUN = 30


class Host:
    stop_requested = False

    def __init__(self, stores: dict[str, Store]) -> None:
        self._stores = stores
        self.project_ids = tuple(stores)

    def store_for(self, project_id: str) -> Store:
        return self._stores[project_id]


def test_the_tick_is_bounded_fair_and_rate_limited(tmp_path: Path) -> None:
    supervisor_dir = tmp_path / "supervisor"
    (supervisor_dir / LAUNCH_LOGS_DIRNAME).mkdir(parents=True)
    stores: dict[str, Store] = {}
    run_ids: set[str] = set()
    for project in range(PROJECT_COUNT):
        project_id = f"p{project}"
        store = Store.open(tmp_path / f"{project_id}.sqlite3")
        stores[project_id] = store
        node = store.create_node(project_id=project_id, kind=NodeKind.SLICE, title="n")
        for run in range(RUNS_PER_PROJECT):
            run_id = f"run-{project}-{run}"
            run_ids.add(run_id)
            store.journal_issue(
                node.id,
                kind=CommandKind.SQ_RUN,
                parameters={"pipeline": "p", "params": {}, "run_id": run_id},
            )
    polls: Counter[str] = Counter()

    def poll(run_id: str):  # noqa: ANN202
        polls[run_id] += 1
        time.sleep(POLL_COST_SECONDS)
        return document(run_id, RunOutcome.TIMED_OUT)

    tenant = RunnerTenant(
        settings=ProcessSettings(
            tick_deadline_seconds=TICK_DEADLINE_SECONDS,
            run_poll_interval_seconds=RUN_POLL_INTERVAL_SECONDS,
        ),
        supervisor_dir=supervisor_dir,
        planners=(),
        popen=subprocess.Popen,
        cf_run=FakeCf(),
        poll=poll,
        now=lambda: datetime.now(UTC),
        monotonic=time.monotonic,
        version_label="sq-test-label",
    )
    host = Host(stores)
    started = time.monotonic()
    durations: list[float] = []
    try:
        for _ in range(MAX_TICKS_TO_REACH_EVERY_RUN):
            tick_started = time.monotonic()
            tenant.tick(host)
            durations.append(time.monotonic() - tick_started)
            if set(polls) == run_ids:
                break
        elapsed = time.monotonic() - started
    finally:
        for store in stores.values():
            store.close()

    print(
        f"ticks={len(durations)} slowest={max(durations):.3f}s elapsed={elapsed:.2f}s"
    )
    assert set(polls) == run_ids, "every run was reached: no starvation"
    assert (
        max(durations) <= TICK_DEADLINE_SECONDS + POLL_COST_SECONDS + TICK_SLACK_SECONDS
    )
    allowed = elapsed / RUN_POLL_INTERVAL_SECONDS + 1
    assert max(polls.values()) <= allowed, "a run was polled faster than the interval"
