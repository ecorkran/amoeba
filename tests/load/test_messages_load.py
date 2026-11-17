"""The message operations under concurrent processes (slice 240, D4, D5, D7).

Many processes, released together on one store, each ``send`` to a shared recipient,
``accept`` their own request and read the ``inbox``; several more race to ``accept``
one shared request. Correctness: no call ends ``busy``, every ``send`` is stored,
exactly one shared accept wins, delivery numbers are unique and complete, and every
``inbox`` snapshot is consistent. Timing: every call stays below the store-wait bound
of its operation (the ``cf`` stub answers at once, so the bound is the store's busy
waits), and no ``cf`` call runs while the write lock is held.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT
from live_environment import process_environment
from operations.message_support import (
    CONFIG,
    RECIPIENT,
    RECIPIENT_NAME,
    SENDER,
    THIRD,
    message_cf,
    message_deps,
    send_note_as_sender,
    send_request_as_sender,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY
from process_containment import contained_popen
from store.message_support import NOW, PROGRAM, seed_members, send_request

from amoeba.operations.cancel import cancel
from amoeba.operations.inbox import inbox
from amoeba.operations.message_models import (
    CancelOutcome,
    InboxOutcome,
    ReplyOutcome,
    SendOutcome,
)
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.reply import reply
from amoeba.store.deliveries import highest_assigned_seq
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from load.lock_probe import write_lock_is_held
from load.messages_worker import (
    BUSY,
    GATE_FILE,
    MIXED,
    NOTES,
    NOTES_PER_WORKER,
    SHARED,
    SHARED_REQUEST_ID,
)

WORKER = Path(__file__).with_name("messages_worker.py")
TESTS_DIRECTORY = Path(__file__).parents[1]
MIXED_PROCESSES = 8
SHARED_PROCESSES = 6
READY_TIMEOUT_SECONDS = 90.0
FINISH_TIMEOUT_SECONDS = 90.0
#: ``send``, ``reply`` and ``cancel`` wait for the legacy-move lock, the open and the
#: transaction: three busy waits (``MESSAGE_STORE_WAITS``, 11.6).
WRITE_BOUND_SECONDS = 3 * BUSY_TIMEOUT_SECONDS
#: ``inbox`` only reads: a reader never waits for a writer beyond one busy timeout.
READ_BOUND_SECONDS = BUSY_TIMEOUT_SECONDS


def _start(
    store_path: Path, gate: Path, mode: str, number: int
) -> subprocess.Popen[str]:
    environment = process_environment(os.environ, PYTHONPATH=str(TESTS_DIRECTORY))
    return contained_popen(
        [sys.executable, str(WORKER), str(store_path), str(gate), mode, str(number)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )


def _run_workers(tmp_path: Path) -> tuple[Path, list[list[dict[str, Any]]]]:
    """The seeded store and each worker's calls, in start order, mixed workers first."""
    store_path = tmp_path / "home" / "amoeba.sqlite3"
    with Store.open(store_path) as store, store.write() as transaction:
        seed_members(transaction, SENDER, RECIPIENT, THIRD)
        send_request(
            transaction,
            SHARED_REQUEST_ID,
            from_member=SENDER,
            to_member=RECIPIENT,
            now=NOW,
        )
    modes = [MIXED] * MIXED_PROCESSES + [SHARED] * SHARED_PROCESSES
    return store_path, _run_processes(store_path, tmp_path / "gate", modes)


def _run_processes(
    store_path: Path, gate: Path, modes: list[str]
) -> list[list[dict[str, Any]]]:
    """Start one worker per mode, release them together and return each one's calls."""
    gate.mkdir()
    workers = [
        _start(store_path, gate, mode, number) for number, mode in enumerate(modes)
    ]
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while len(list(gate.glob("ready-*"))) < len(workers):
        assert time.monotonic() < deadline, "workers did not all start"
        time.sleep(0.01)
    (gate / GATE_FILE).touch()
    calls: list[list[dict[str, Any]]] = []
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=FINISH_TIMEOUT_SECONDS)
        assert worker.returncode == 0, stderr
        calls.append(json.loads(stdout))
    return calls


@pytest.fixture(scope="module")
def burst(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, list[list[dict[str, Any]]]]:
    return _run_workers(tmp_path_factory.mktemp("messages-load"))


def _all(calls: list[list[dict[str, Any]]], operation: str) -> list[dict[str, Any]]:
    return [
        call for worker in calls for call in worker if call["operation"] == operation
    ]


def test_no_call_ends_busy_and_every_send_is_stored(
    burst: tuple[Path, list[list[dict[str, Any]]]],
) -> None:
    store_path, calls = burst

    assert not [call for worker in calls for call in worker if call["outcome"] == BUSY]
    sends = _all(calls, "send")
    assert [call["outcome"] for call in sends] == [
        SendOutcome.SENT.value
    ] * MIXED_PROCESSES
    with Store.open(store_path) as store, store.read() as transaction:
        stored = {
            str(row[0])
            for row in transaction.execute("SELECT message_id FROM messages")
        }
    assert stored == {f"req-{n}" for n in range(MIXED_PROCESSES)} | {SHARED_REQUEST_ID}


def test_every_own_accept_applies_and_exactly_one_shared_accept_wins(
    burst: tuple[Path, list[list[dict[str, Any]]]],
) -> None:
    _, calls = burst

    own = [
        call
        for worker in calls[:MIXED_PROCESSES]
        for call in worker
        if call["operation"] == "accept"
    ]
    shared = [call for worker in calls[MIXED_PROCESSES:] for call in worker]
    assert [call["outcome"] for call in own] == [
        ReplyOutcome.APPLIED.value
    ] * MIXED_PROCESSES
    outcomes = sorted(call["outcome"] for call in shared)
    assert outcomes == [ReplyOutcome.APPLIED.value] + [ReplyOutcome.REJECTED.value] * (
        SHARED_PROCESSES - 1
    )
    losers = [call for call in shared if call["outcome"] == ReplyOutcome.REJECTED.value]
    assert {call["rejection"] for call in losers} == {RejectCode.ALREADY_ACCEPTED.value}


def test_delivery_numbers_are_unique_and_the_highest_equals_the_count(
    burst: tuple[Path, list[list[dict[str, Any]]]],
) -> None:
    store_path, _ = burst

    with Store.open(store_path) as store, store.read() as transaction:
        seqs = [
            int(row[0]) for row in transaction.execute("SELECT seq FROM deliveries")
        ]
        highest = highest_assigned_seq(transaction)
    assert len(seqs) == len(set(seqs))
    assert highest == len(seqs) == max(seqs)


def test_every_inbox_snapshot_is_consistent(
    burst: tuple[Path, list[list[dict[str, Any]]]],
) -> None:
    store_path, calls = burst
    with Store.open(store_path) as store, store.read() as transaction:
        final = highest_assigned_seq(transaction)

    for call in _all(calls, "inbox"):
        assert call["as_of_seq"] <= final
        assert all(seq <= call["as_of_seq"] for seq in call["delivery_seqs"])
        assert call["delivery_seqs"] == sorted(call["delivery_seqs"])
    from_zero = [call for call in _all(calls, "inbox") if call["delivery_seqs"]]
    # Each mixed worker sent first, so its read from 0 holds at least that delivery.
    assert len(from_zero) == MIXED_PROCESSES
    for call in from_zero:
        # Read from 0, the requests are exactly those the deliveries concern.
        assert set(call["request_ids"]) == set(call["delivery_message_ids"])


def test_every_call_stays_within_its_store_wait_bound(
    burst: tuple[Path, list[list[dict[str, Any]]]],
) -> None:
    _, calls = burst

    for operation in ("send", "accept"):
        slowest = max(call["seconds"] for call in _all(calls, operation))
        assert slowest < WRITE_BOUND_SECONDS, operation
    assert max(call["seconds"] for call in _all(calls, "inbox")) < READ_BOUND_SECONDS


class _LockProbingCf:
    """The message ``cf`` double, recording whether the write lock was held at each
    call. Run in one process, so a held lock is this call's own."""

    def __init__(self, database: Path, directory_fixture: str) -> None:
        self._database = database
        self._inner = message_cf(directory_fixture)
        self.held_at_call: list[bool] = []

    def __call__(self, argv: Any, **kwargs: Any) -> Any:
        self.held_at_call.append(write_lock_is_held(self._database))
        return self._inner(argv, **kwargs)


def test_no_cf_call_runs_while_the_write_lock_is_held(tmp_path: Path) -> None:
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        with store.write() as transaction:
            seed_members(transaction, SENDER, RECIPIENT, THIRD)
        in_member = _LockProbingCf(store.path, DEFAULT_WORKTREE)
        in_none = _LockProbingCf(store.path, OUTSIDE_ANY_PROJECT)
        sender = message_deps(tmp_path, SettableClock(), in_member)
        addressee = message_deps(tmp_path, SettableClock(), in_none)
        accept = {"id": "ask", "action": "accept", "member": RECIPIENT_NAME}

        sent = send_request_as_sender(store, sender, "ask")
        applied = reply(store, CONFIG, accept, directory=DIRECTORY, deps=addressee)
        listed = inbox(store, {}, directory=DIRECTORY, deps=sender)
        cancelled = cancel(
            store, CONFIG, {"id": "ask"}, directory=DIRECTORY, deps=sender
        )

    assert sent.outcome is SendOutcome.SENT
    assert applied.outcome is ReplyOutcome.APPLIED
    assert listed.outcome is InboxOutcome.LISTED
    assert cancelled.outcome is CancelOutcome.CANCELLED
    probed = [*in_member.held_at_call, *in_none.held_at_call]
    assert len(probed) >= 6, "every operation resolves through cf"
    assert not any(probed)


# --- program notes (slice 243, D5's write-lock paragraph) ----------------------

#: The program of the note burst: the sender, ``RECIPIENT``, ``THIRD`` and this many
#: more members, each of whom is a recipient of a program note.
EXTRA_READERS = 3
NOTE_PROCESSES = 6
EXTRA_MEMBERS = tuple(f"note-reader-{number}" for number in range(EXTRA_READERS))


def _note_recipients() -> list[str]:
    return [RECIPIENT, THIRD, *EXTRA_MEMBERS]


NOTE_RECIPIENTS = len(_note_recipients())


@pytest.fixture(scope="module")
def note_burst(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, list[list[dict[str, Any]]]]:
    tmp_path = tmp_path_factory.mktemp("notes-load")
    store_path = tmp_path / "home" / "amoeba.sqlite3"
    with Store.open(store_path) as store, store.write() as transaction:
        seed_members(transaction, SENDER, *_note_recipients())
    return store_path, _run_processes(
        store_path, tmp_path / "gate", [NOTES] * NOTE_PROCESSES
    )


def test_every_program_note_send_is_sent_and_reaches_each_recipient_once(
    note_burst: tuple[Path, list[list[dict[str, Any]]]],
) -> None:
    store_path, calls = note_burst

    sends = [call for worker in calls for call in worker]
    total = NOTE_PROCESSES * NOTES_PER_WORKER
    assert [call["outcome"] for call in sends] == [SendOutcome.SENT.value] * total
    with Store.open(store_path) as store, store.read() as transaction:
        per_member = dict(
            transaction.execute(
                "SELECT member_id, count(*) FROM deliveries GROUP BY member_id"
            ).fetchall()
        )
        seqs = [
            int(row[0]) for row in transaction.execute("SELECT seq FROM deliveries")
        ]
    assert per_member == {member: total for member in _note_recipients()}
    assert SENDER not in per_member
    assert len(seqs) == len(set(seqs)) == total * NOTE_RECIPIENTS


def test_no_program_note_send_waits_beyond_one_store_wait_bound(
    note_burst: tuple[Path, list[list[dict[str, Any]]]],
) -> None:
    _, calls = note_burst

    sends = [call for worker in calls for call in worker]
    assert not [call for call in sends if call["outcome"] == BUSY]
    assert max(call["seconds"] for call in sends) < WRITE_BOUND_SECONDS


def test_no_cf_call_runs_while_a_program_note_is_written(tmp_path: Path) -> None:
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        with store.write() as transaction:
            seed_members(transaction, SENDER, *_note_recipients())
        probing = _LockProbingCf(store.path, DEFAULT_WORKTREE)
        deps = message_deps(tmp_path, SettableClock(), probing)

        sent = send_note_as_sender(store, deps, "news", to=None, to_program=PROGRAM)

    assert sent.outcome is SendOutcome.SENT
    assert probing.held_at_call, "send resolves the sender through cf"
    assert not any(probing.held_at_call)
