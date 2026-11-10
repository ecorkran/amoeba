"""Eight processes add different members to one program in one new store."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from live_environment import process_environment
from process_containment import contained_popen

from amoeba.operations.set_up_models import SetUpOutcome
from amoeba.store.programs import members_of
from amoeba.store.store import Store
from operations.set_up_worker import BUSY, GATE_FILE

WORKER = Path(__file__).with_name("set_up_worker.py")
TESTS_DIRECTORY = Path(__file__).parents[1]
PROCESS_COUNT = 8
READY_TIMEOUT_SECONDS = 60.0
FINISH_TIMEOUT_SECONDS = 60.0


def _start(store_path: Path, gate: Path, number: int) -> subprocess.Popen[str]:
    environment = process_environment(os.environ, PYTHONPATH=str(TESTS_DIRECTORY))
    return contained_popen(
        [sys.executable, str(WORKER), str(store_path), str(gate), str(number)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )


def _wait_until_ready(gate: Path) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while len(list(gate.glob("ready-*"))) < PROCESS_COUNT:
        assert time.monotonic() < deadline, "workers did not all start"
        time.sleep(0.01)


def test_eight_concurrent_set_ups_store_every_applied_member(tmp_path: Path) -> None:
    store_path = tmp_path / "home" / "amoeba.sqlite3"
    gate = tmp_path / "gate"
    gate.mkdir()
    workers = [_start(store_path, gate, number) for number in range(PROCESS_COUNT)]
    _wait_until_ready(gate)
    (gate / GATE_FILE).touch()

    applied: set[str] = set()
    for number, worker in enumerate(workers):
        stdout, stderr = worker.communicate(timeout=FINISH_TIMEOUT_SECONDS)
        assert worker.returncode == 0, stderr
        outcome = json.loads(stdout)["outcome"]
        assert outcome in (SetUpOutcome.APPLIED.value, BUSY), stderr
        if outcome == SetUpOutcome.APPLIED.value:
            applied.add(f"id-{number}")

    assert applied, "no worker reported applied"
    with Store.open(store_path) as store, store.read() as transaction:
        stored = {member.project_id for member in members_of(transaction, "demo")}
    # Every member that reported applied is stored. (A member that reported busy
    # was never written, so the sets are equal.)
    assert stored == applied
