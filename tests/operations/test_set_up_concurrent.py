"""Eight processes add different members to one program in one new store."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from live_environment import process_environment
from process_containment import contained_popen
from store.question_support import NOW, waiting_question

from amoeba.operations.dismiss import dismiss
from amoeba.operations.set_up_models import SetUpOutcome, SetUpProblemCode
from amoeba.store.models import QuestionKey
from amoeba.store.programs import get_member_any, members_of
from amoeba.store.question_closing import member_open_questions
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from operations.set_up_support import run_set_up
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


RACE_ROUNDS = 20
RACE_PROJECTS = [("racer-id", "racer")]
RACE_KEY = QuestionKey("run-race", "2026-11-10T11:00:00+00:00")


def _race_store(path: Path) -> None:
    with Store.open(path) as store:
        run_set_up(
            store,
            {
                "program": "demo",
                "members": [{"project": "racer", "rules_paths": ["CLAUDE.md"]}],
            },
            projects=RACE_PROJECTS,
        )
        with store.write() as transaction:
            insert_question(
                transaction, waiting_question(RACE_KEY, member_id="racer-id"), now=NOW
            )


def _race(path: Path) -> SetUpOutcome:
    """A removal and a ``dismiss`` released together, each on its own connection.

    Run in a thread pool, so an exception in either worker is re-raised here.
    """
    gate = threading.Barrier(2)

    def remove() -> SetUpOutcome:
        with Store.open(path) as store:
            gate.wait()
            result = run_set_up(
                store,
                {"program": "demo", "remove": {"members": ["racer"]}},
                projects=RACE_PROJECTS,
            )
        if result.outcome is SetUpOutcome.REJECTED:
            assert [p.code for p in result.problems] == [
                SetUpProblemCode.MEMBER_HAS_OPEN_QUESTIONS
            ]
        return result.outcome

    def dismiss_it() -> None:
        with Store.open(path) as store:
            gate.wait()
            dismiss(
                store,
                {"run_id": RACE_KEY.run_id, "reason": "racing"},
                clock=lambda: NOW,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        removal = pool.submit(remove)
        dismissal = pool.submit(dismiss_it)
        dismissal.result(timeout=FINISH_TIMEOUT_SECONDS)
        return removal.result(timeout=FINISH_TIMEOUT_SECONDS)


def test_a_racing_removal_and_dismiss_never_strand_an_open_question(
    tmp_path: Path,
) -> None:
    seen: set[SetUpOutcome] = set()
    for round_number in range(RACE_ROUNDS):
        path = tmp_path / f"round-{round_number}" / "amoeba.sqlite3"
        path.parent.mkdir()
        _race_store(path)

        seen.add(_race(path))

        with Store.open(path) as store, store.read() as transaction:
            member = get_member_any(transaction, "racer-id")
            assert member is not None
            if member.removed_at is not None:
                assert member_open_questions(transaction, "racer-id") == ()
    # Either order is legal; the invariant above is what must hold in both.
    assert seen <= {SetUpOutcome.APPLIED, SetUpOutcome.REJECTED}
