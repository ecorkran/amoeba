"""``start_ended_held`` under concurrent callers and a busy store (slice 242, D7).

Several callers, each with its own connection as separate processes would have, run
the start trigger together over more ended held rows than one call may start, while
one more connection keeps the store busy with short writes. Each call stays inside
``START_BOUND_SECONDS``, none starts more than ``MAX_STARTS_PER_CALL``, no row is
started twice within ``answering_wait_seconds`` (the clock does not move, so twice
would mean twice at once), and after enough rounds every row has been started.
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from operations.pause_support import FakeChild, build_deps
from store.message_support import send_request
from store.question_support import (
    MEMBER_ID,
    OTHER_MEMBER_ID,
    insert_held_row,
    seed_members,
)
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.processes import WaitableChild
from amoeba.operations.request_release import (
    MAX_STARTS_PER_CALL,
    START_BOUND_SECONDS,
    start_ended_held,
)
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.models import QuestionKey
from amoeba.store.questions import get_question
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs

ROWS = 3 * MAX_STARTS_PER_CALL
CALLERS = 4
#: Rounds of all callers together; enough for every row whatever the interleaving.
ROUNDS = ROWS
#: How long the busy writer holds each of its short write transactions.
BUSY_HOLD_SECONDS = 0.01
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
SCRIPT = Path("/installed/bin/amoeba")


def _seed(path: Path) -> list[QuestionKey]:
    keys = [
        QuestionKey(f"run-{n:02d}", "2026-11-10T11:00:00+00:00") for n in range(ROWS)
    ]
    with open_local_store(path) as store:
        seed_members(store)
        with store.write() as transaction:
            for number, key in enumerate(keys):
                request_id = f"request-{number}"
                send_request(
                    transaction,
                    request_id,
                    from_member=MEMBER_ID,
                    to_member=OTHER_MEMBER_ID,
                )
                message = get_message(transaction, request_id)
                assert message is not None
                change_state(
                    transaction, message, RequestState.DECLINED,
                    DeliveryEvent.DECLINED, OTHER_MEMBER_ID, NOW, StateFields(),
                )  # fmt: skip
                insert_held_row(transaction, key, request_id=request_id, now=NOW)
    return keys


def test_concurrent_callers_start_each_row_once_within_the_bound(
    tmp_path: Path,
) -> None:
    path = tmp_path / "amoeba.sqlite3"
    keys = _seed(path)
    started: Counter[str] = Counter()
    lock = threading.Lock()
    #: Each caller's starts within its current call.
    this_call = threading.local()

    def count(
        argv: list[str] | tuple[str, ...], _cwd: Path, _logs: LaunchLogs
    ) -> WaitableChild | LaunchError:
        with lock:
            started[argv[-1]] += 1
        this_call.starts += 1
        return FakeChild(0)

    rig = build_deps(tmp_path, polls={}, spawns=[])
    rig.clock.now = NOW
    deps = replace(rig.deps, spawn=count, amoeba_script=lambda: SCRIPT)
    config = user_config()
    stop = threading.Event()

    def keep_busy() -> None:
        with open_local_store(path) as store:
            while not stop.is_set():
                with store.write():
                    time.sleep(BUSY_HOLD_SECONDS)

    def call_rounds(_caller: int) -> list[tuple[float, int]]:
        calls: list[tuple[float, int]] = []
        with open_local_store(path) as store:
            for _ in range(ROUNDS):
                this_call.starts = 0
                began = time.monotonic()
                start_ended_held(store, config, deps)
                calls.append((time.monotonic() - began, this_call.starts))
        return calls

    busy = threading.Thread(target=keep_busy)
    busy.start()
    try:
        with ThreadPoolExecutor(max_workers=CALLERS) as pool:
            per_caller = list(pool.map(call_rounds, range(CALLERS)))
    finally:
        stop.set()
        busy.join()

    calls = [call for caller in per_caller for call in caller]
    assert max(seconds for seconds, _ in calls) < START_BOUND_SECONDS
    assert max(made for _, made in calls) <= MAX_STARTS_PER_CALL
    assert sum(made for _, made in calls) == ROWS
    assert max(started.values()) == 1, "a row was started twice"
    assert set(started) == {key.run_id for key in keys}
    with open_local_store(path) as store, store.read() as transaction:
        for key in keys:
            row = get_question(transaction, key)
            assert row is not None
            assert row.start_attempted_at == NOW
