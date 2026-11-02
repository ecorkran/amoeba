"""A Runner tick that keeps failing must not spin the resident loop or flood the log.

The loop skips its idle wait after a tick that reports work. A failing tick used
to report work, so a fault that never cleared ran the loop flat out, one full
traceback per pass (measured at about 3.7 MB/s, over 300 GB a day).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from amoeba.store import Store
from runner.tick_support import Rig, StoreHost, tenant_for

TENANT_LOGGER = "amoeba.runner.tenant"


class FailingPlanner:
    """A planner that raises while ``failing`` is set, as a broken world would."""

    def __init__(self) -> None:
        self.failing = True

    def plan(self, view: Any) -> list[Any]:
        if self.failing:
            raise RuntimeError("the world this tick needs is gone")
        return []


@pytest.fixture
def planner() -> FailingPlanner:
    return FailingPlanner()


@pytest.fixture
def rig(tmp_path: Path, store: Store, planner: FailingPlanner) -> Rig:
    built = Rig(tmp_path, store)
    built.planners = (planner,)
    return built


def _tracebacks(caplog: pytest.LogCaptureFixture) -> int:
    return sum(
        1
        for record in caplog.records
        if record.name == TENANT_LOGGER and record.exc_info is not None
    )


def test_a_failing_tick_reports_no_work_so_the_loop_idles(
    rig: Rig, store: Store
) -> None:
    tenant = tenant_for(rig)

    results = {tenant.tick(StoreHost(store)) for _ in range(5)}

    assert results == {False}


def test_a_repeated_identical_failure_logs_a_traceback_only_now_and_then(
    rig: Rig, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    tenant = tenant_for(rig)
    ticks = 40

    with caplog.at_level(logging.WARNING, logger=TENANT_LOGGER):
        for _ in range(ticks):
            tenant.tick(StoreHost(store))

    failures = [r for r in caplog.records if r.name == TENANT_LOGGER]
    assert len(failures) == ticks, "every failure is still recorded as one line"
    assert 1 <= _tracebacks(caplog) <= 7, "tracebacks thin out as it repeats"


def test_a_tick_that_succeeds_resets_the_count(
    rig: Rig, store: Store, planner: FailingPlanner, caplog: pytest.LogCaptureFixture
) -> None:
    tenant = tenant_for(rig)
    with caplog.at_level(logging.WARNING, logger=TENANT_LOGGER):
        for _ in range(8):
            tenant.tick(StoreHost(store))
        planner.failing = False
        tenant.tick(StoreHost(store))
        before = _tracebacks(caplog)
        planner.failing = True
        tenant.tick(StoreHost(store))

    assert _tracebacks(caplog) == before + 1, "a fresh failure gets its traceback"
