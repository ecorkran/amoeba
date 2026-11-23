"""Two sends at once never start two wakes (slice 244, D2, D11).

``claim_wake`` is one ``BEGIN IMMEDIATE`` transaction, so ``WRITERS`` senders, each
with its own connection as separate processes would have, that send a request to one
member with a wake command at once produce one row and one spawn; every request is
stored and waits in the member's inbox (the guarantee the second sender gets). Sends to
different members each wake their own. No send takes longer than the wake step's bound
plus ``send``'s own, and the burst finishes within a budget.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

from cf_fixtures import DEFAULT_WORKTREE
from operations.message_support import message_deps
from operations.pause_support import FakeChild
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY, RECORDED_ID, FakeCf
from store.message_support import NOW, PROGRAM, seed_members
from store.seed import insert_member
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.names import OperationName
from amoeba.operations.processes import WaitableChild
from amoeba.operations.send import send
from amoeba.operations.wake import WAKE_BOUND_SECONDS
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs
from amoeba.wiring_messages import worst_case_seconds

WRITERS = 8
#: The whole burst, with generous headroom for a slow runner; one slower than this is
#: lock contention that has gone wrong.
BURST_BUDGET_SECONDS = 30.0
COMMAND = "wake-agent --max-seconds 60"
SCRIPT = Path("/installed/bin/amoeba")
CONFIG = user_config()


@dataclass(frozen=True)
class Burst:
    slowest_send_seconds: float
    elapsed_seconds: float
    spawned: list[Sequence[str]]


class _CountingSpawn:
    """A spawn that records its calls under a lock, as threads call it together."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: list[Sequence[str]] = []

    def __call__(
        self, argv: Sequence[str], cwd: Path, logs: LaunchLogs
    ) -> WaitableChild | LaunchError:
        with self._lock:
            self.calls.append(list(argv))
        return FakeChild(None)


def _targets(count: int) -> list[tuple[str, str]]:
    return [(f"load-member-{n}-id", f"load-member-{n}-name") for n in range(count)]


def _seed(path: Path, members: Sequence[tuple[str, str]]) -> None:
    with open_local_store(path) as setup, setup.write() as transaction:
        seed_members(transaction, RECORDED_ID)
        for project_id, _ in members:
            insert_member(
                transaction,
                project_id=project_id,
                program_id=PROGRAM,
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=NOW,
                updated_at=NOW,
                wake_command=COMMAND,
            )


def _burst(tmp_path: Path, targets: Sequence[tuple[str, str]]) -> Burst:
    """Writer ``n`` sends one request to ``targets[n % len(targets)]``; all start
    together."""
    path = tmp_path / "amoeba.sqlite3"
    _seed(path, targets)
    spawn = _CountingSpawn()
    deps = replace(
        message_deps(
            tmp_path,
            SettableClock(),
            FakeCf(directory_fixture=DEFAULT_WORKTREE, projects=list(targets)),
        ),
        spawn=spawn,
        amoeba_script=lambda: SCRIPT,
    )
    gate = threading.Barrier(WRITERS)

    def send_one(number: int) -> float:
        _, name = targets[number % len(targets)]
        with open_local_store(path) as store:
            gate.wait(timeout=WAKE_BOUND_SECONDS)
            started = time.monotonic()
            result = send(
                store,
                CONFIG,
                {"id": f"load-{number}", "to": name, "subject": "s", "body": "b"},
                directory=DIRECTORY,
                deps=deps,
            )
            elapsed = time.monotonic() - started
        assert result.wake_problem is None
        return elapsed

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=WRITERS) as pool:
        durations = list(pool.map(send_one, range(WRITERS)))
    return Burst(max(durations), time.monotonic() - started, spawn.calls)


def _count(path: Path, query: str) -> list[tuple[object, ...]]:
    with open_local_store(path) as store, store.read() as transaction:
        return [tuple(row) for row in transaction.execute(query).fetchall()]


def test_writers_sending_to_one_member_at_once_start_one_wake(tmp_path: Path) -> None:
    burst = _burst(tmp_path, _targets(1))

    path = tmp_path / "amoeba.sqlite3"
    assert len(burst.spawned) == 1
    assert _count(path, "SELECT count(*) FROM wakes") == [(1,)]
    assert _count(path, "SELECT count(*) FROM messages WHERE state = 'open'") == [
        (WRITERS,)
    ]
    send_bound = worst_case_seconds(OperationName.SEND)
    assert burst.slowest_send_seconds < WAKE_BOUND_SECONDS + send_bound
    assert burst.elapsed_seconds < BURST_BUDGET_SECONDS


def test_writers_sending_to_different_members_each_start_their_own_wake(
    tmp_path: Path,
) -> None:
    burst = _burst(tmp_path, _targets(WRITERS))

    path = tmp_path / "amoeba.sqlite3"
    assert len(burst.spawned) == WRITERS
    assert _count(path, "SELECT count(*) FROM wakes") == [(WRITERS,)]
    assert _count(path, "SELECT count(DISTINCT member_id) FROM wakes") == [(WRITERS,)]
    assert burst.elapsed_seconds < BURST_BUDGET_SECONDS
