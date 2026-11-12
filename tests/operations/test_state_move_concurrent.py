"""Two processes move one legacy home at the same time (slice 228, D2)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from live_environment import process_environment
from process_containment import contained_popen

from operations.state_move_support import (
    SELECT_ANSWERS,
    legacy_leftovers,
    make_layout,
    rows,
    seed_legacy_home,
)
from operations.state_move_worker import GATE_FILE

WORKER = Path(__file__).with_name("state_move_worker.py")
TESTS_DIRECTORY = Path(__file__).parents[1]
PROCESS_COUNT = 2
READY_TIMEOUT_SECONDS = 60.0
FINISH_TIMEOUT_SECONDS = 60.0


def _start(legacy: Path, state: Path, gate: Path, number: int) -> subprocess.Popen[str]:
    environment = process_environment(os.environ, PYTHONPATH=str(TESTS_DIRECTORY))
    return contained_popen(
        [sys.executable, str(WORKER), str(legacy), str(state), str(gate), str(number)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )


def test_two_processes_move_once_and_both_end_with_the_complete_store(
    tmp_path: Path,
) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)
    expected = [row[:2] for row in rows(legacy_store, SELECT_ANSWERS)]
    gate = tmp_path / "gate"
    gate.mkdir()
    assert layout.legacy_home is not None
    workers = [
        _start(layout.legacy_home, layout.state_home, gate, number)
        for number in range(PROCESS_COUNT)
    ]
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while len(list(gate.glob("ready-*"))) < PROCESS_COUNT:
        assert time.monotonic() < deadline, "workers did not all start"
        time.sleep(0.01)
    (gate / GATE_FILE).touch()

    reports: list[dict[str, bool]] = []
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=FINISH_TIMEOUT_SECONDS)
        assert worker.returncode == 0, stderr
        reports.append(json.loads(stdout))

    assert sum(report["store_moved"] for report in reports) == 1
    assert [row[:2] for row in rows(layout.store_path, SELECT_ANSWERS)] == expected
    assert not legacy_store.exists()
    assert legacy_leftovers(layout) == ["config.yaml"]
