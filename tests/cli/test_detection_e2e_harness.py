"""Smoke check: the end-to-end harness can seed, run, follow, and stop."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from detection_e2e_harness import DetectionE2E

PROJECT = "demo"


@pytest.fixture
def e2e(supervisor_dir: Path, tmp_path: Path) -> Iterator[DetectionE2E]:
    harness = DetectionE2E(supervisor_dir, tmp_path)
    yield harness
    harness.cleanup()


def test_the_harness_seeds_runs_follows_and_stops(e2e: DetectionE2E) -> None:
    process = e2e.start_process()
    e2e.create_project(PROJECT)
    e2e.stop_process(process)
    e2e.seed_demo()

    process = e2e.start_process()
    follower = e2e.start_follower(PROJECT)
    follower.wait_for(lambda lines: len(lines) >= 1)
    e2e.stop_process(process)
    assert follower.lines
