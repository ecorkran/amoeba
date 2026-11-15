"""Two processes accept one request at once: exactly one wins (slice 240, D4)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from live_environment import process_environment
from process_containment import contained_popen
from store.message_support import NOW, seed_members, send_request

from amoeba.operations.message_models import ReplyOutcome
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.messages import get_message
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import RequestState
from operations.message_support import RECIPIENT, SENDER, THIRD
from operations.reply_worker import GATE_FILE

WORKER = Path(__file__).with_name("reply_worker.py")
TESTS_DIRECTORY = Path(__file__).parents[1]
PROCESS_COUNT = 2
REQUEST_ID = "contested"
READY_TIMEOUT_SECONDS = 60.0
FINISH_TIMEOUT_SECONDS = 60.0


def _start(store_path: Path, gate: Path, number: int) -> subprocess.Popen[str]:
    environment = process_environment(os.environ, PYTHONPATH=str(TESTS_DIRECTORY))
    return contained_popen(
        [
            sys.executable,
            str(WORKER),
            str(store_path),
            str(gate),
            REQUEST_ID,
            str(number),
        ],
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


def test_two_accepts_at_once_have_exactly_one_winner(tmp_path: Path) -> None:
    store_path = tmp_path / "home" / "amoeba.sqlite3"
    gate = tmp_path / "gate"
    gate.mkdir()
    with Store.open(store_path) as store, store.write() as transaction:
        seed_members(transaction, SENDER, RECIPIENT, THIRD)
        send_request(
            transaction, REQUEST_ID, from_member=SENDER, to_member=RECIPIENT, now=NOW
        )
    workers = [_start(store_path, gate, number) for number in range(PROCESS_COUNT)]
    _wait_until_ready(gate)
    (gate / GATE_FILE).touch()

    results: list[dict[str, Any]] = []
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=FINISH_TIMEOUT_SECONDS)
        assert worker.returncode == 0, stderr
        results.append(json.loads(stdout))

    outcomes = sorted(result["outcome"] for result in results)
    assert outcomes == [ReplyOutcome.APPLIED.value, ReplyOutcome.REJECTED.value]
    (loser,) = (r for r in results if r["outcome"] == ReplyOutcome.REJECTED.value)
    assert loser["rejection"] == RejectCode.ALREADY_ACCEPTED.value
    with Store.open(store_path) as store, store.read() as transaction:
        stored = get_message(transaction, REQUEST_ID)
        accepted = transaction.execute(
            "SELECT count(*) FROM deliveries WHERE event = 'accepted'"
        ).fetchone()
    assert stored is not None and stored.state is RequestState.ACCEPTED
    assert stored.accepted_at is not None
    assert encode_timestamp(stored.accepted_at) in loser["problems"][0]
    assert accepted is not None and accepted[0] == 1
