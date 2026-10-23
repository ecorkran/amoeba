"""The crash harness runs a scenario with no kill, end to end."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.store import PARAM_RUN_ID, JournalOutcome
from runner.crash_harness import CrashHarness, RunSettings


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[CrashHarness]:
    created = CrashHarness(tmp_path)
    yield created
    created.close()


def test_a_run_with_no_kill_is_launched_confirmed_and_recorded(
    harness: CrashHarness,
) -> None:
    process = harness.start(RunSettings(run_seconds=0.3))

    entry = harness.wait_for_resolution()

    assert entry.outcome is JournalOutcome.COMPLETED
    assert entry.node_id == harness.node_ids[0]
    assert entry.result is not None and entry.result["outcome"] == "completed"
    run_id = str(entry.parameters[PARAM_RUN_ID])
    assert harness.sq_run_calls(run_id) == 1
    assert harness.open_blocks(entry.node_id) == []
    harness.stop(process)
    assert process.host.returncode == 0


def test_a_node_is_launched_once_even_after_its_run_is_recorded(
    harness: CrashHarness,
) -> None:
    process = harness.start(RunSettings(run_seconds=0.1))
    harness.wait_for_resolution()

    harness.stop(process)
    second = harness.start(RunSettings(run_seconds=0.1))
    harness.stop(second)

    assert harness.all_sq_run_calls() == 1
