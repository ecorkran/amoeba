"""`send`'s wake step: when a wake starts and when it does not (244, D2, D4, D5)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from store.message_support import NOW, PROGRAM
from store.seed import insert_member
from store.wake_support import confirmed_session

from amoeba.amoeba_script import AmoebaScriptMissing
from amoeba.operations import wake as wake_module
from amoeba.operations.message_models import SendOutcome
from amoeba.operations.message_sweep import sweep_messages
from amoeba.store.errors import StoreBusyError
from amoeba.store.models import Session
from amoeba.store.programs import remove_member
from amoeba.store.sessions import upsert_session
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState, WakeOutcome
from amoeba.store.wakes import WAKE_WINDOW, wake_summary
from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.launch import LaunchError
from operations.message_support import (
    RECIPIENT,
    RECIPIENT_NAME,
    SENDER_NAME,
    open_message_store,
    send_note_as_sender,
)
from operations.pause_support import FakeChild
from operations.wake_send_support import (
    CHECKOUT,
    GHOST,
    MAX_WAKES,
    SCRIPT,
    TICK,
    WakeRig,
    accept,
    at,
    give_command,
    inbox_of,
    send_request,
    wake_config,
    wake_rig,
)

MARKER_SUBJECT = "SUBJECT-MARKER-TEXT"
MARKER_BODY = "BODY-MARKER-TEXT"
CHAIN_WAIT = timedelta(hours=1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    for opened in open_message_store(tmp_path):
        give_command(opened)
        yield opened


@pytest.fixture
def rig(tmp_path: Path) -> WakeRig:
    return wake_rig(tmp_path)


def _wakes(store: Store) -> list[tuple[str, str | None, str | None]]:
    """Each row as ``(wake_id, outcome, detail)``, oldest first."""
    with store.read() as transaction:
        return [
            (str(row[0]), row[1], row[2])
            for row in transaction.execute(
                "SELECT wake_id, outcome, detail FROM wakes ORDER BY started_at"
            )
        ]


def _request_state(store: Store, request_id: str) -> RequestState:
    with store.read() as transaction:
        row = transaction.execute(
            "SELECT state FROM messages WHERE message_id = ?", (request_id,)
        ).fetchone()
    assert row is not None
    return RequestState(row[0])


def test_a_request_to_a_member_with_a_command_claims_one_row_and_spawns_the_wrapper(
    store: Store, rig: WakeRig
) -> None:
    result = send_request(store, rig, "ask")

    assert result.outcome is SendOutcome.SENT
    assert result.wake_problem is None
    ((wake_id, outcome, _),) = _wakes(store)
    assert outcome is None
    (call,) = rig.spawner.calls
    assert call.argv == (str(SCRIPT), "wake-run", wake_id)
    assert call.cwd == CHECKOUT
    stem = rig.deps.logs_dir / "wake" / wake_id
    assert call.logs.stdout == Path(f"{stem}.stdout.log")
    assert call.logs.stderr == Path(f"{stem}.stderr.log")


def test_a_second_send_while_the_wake_is_live_spawns_nothing(
    store: Store, rig: WakeRig
) -> None:
    send_request(store, rig, "first")

    result = send_request(store, rig, "second")

    assert result.outcome is SendOutcome.SENT
    assert len(rig.spawner.calls) == 1
    assert len(_wakes(store)) == 1


def test_a_push_confirmed_session_blocks_the_wake(store: Store, rig: WakeRig) -> None:
    with store.write() as transaction:
        confirmed_session(transaction, RECIPIENT, rig.clock.now)

    send_request(store, rig, "ask")

    assert rig.spawner.calls == []
    assert _wakes(store) == []


def test_a_session_without_push_confirmation_does_not_block(
    store: Store, rig: WakeRig
) -> None:
    with store.write() as transaction:
        upsert_session(
            transaction,
            Session(
                session_id="plain",
                member_id=RECIPIENT,
                client="claude-code",
                directory="/work",
                started_at=rig.clock.now,
                heartbeat_at=rig.clock.now,
                push_confirmed_at=None,
            ),
        )

    send_request(store, rig, "ask")

    assert len(rig.spawner.calls) == 1


def test_a_recipient_with_no_command_is_never_woken(store: Store, rig: WakeRig) -> None:
    give_command(store, RECIPIENT, None)

    result = send_request(store, rig, "ask")

    assert result.outcome is SendOutcome.SENT
    assert rig.spawner.calls == []
    assert _wakes(store) == []


def test_a_removed_member_is_refused_and_nothing_starts(
    store: Store, rig: WakeRig
) -> None:
    with store.write() as transaction:
        remove_member(transaction, RECIPIENT, NOW)

    result = send_request(store, rig, "ask")

    assert result.outcome is SendOutcome.REJECTED
    assert rig.spawner.calls == []


def test_a_note_to_a_member_with_a_command_starts_nothing(
    store: Store, rig: WakeRig
) -> None:
    result = send_note_as_sender(store, rig.deps, "fyi")

    assert result.note is not None
    assert rig.spawner.calls == []
    assert _wakes(store) == []


def test_no_checkout_here_gets_no_wake_row_and_the_request_stays_open(
    store: Store, rig: WakeRig
) -> None:
    with store.write() as transaction:
        insert_member(
            transaction,
            project_id=GHOST,
            program_id=PROGRAM,
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=NOW,
            updated_at=NOW,
        )

    result = send_request(store, rig, "ask", to=GHOST)

    # The member has no checkout on this machine, so no wake is claimed (261 D9, a
    # departure from 244, where the claim ended as ``start_failed``).
    assert result.outcome is SendOutcome.SENT
    assert rig.spawner.calls == []
    assert _wakes(store) == []
    assert _request_state(store, "ask") is RequestState.OPEN


def test_a_launch_error_ends_the_row_start_failed_and_the_request_stays_open(
    tmp_path: Path, store: Store
) -> None:
    error = LaunchError(LaunchFailure.SPAWN_ERROR, "the checkout is gone")
    rig = wake_rig(tmp_path, results=[error])

    result = send_request(store, rig, "ask")

    assert result.outcome is SendOutcome.SENT
    ((_, outcome, detail),) = _wakes(store)
    assert (outcome, detail) == (WakeOutcome.START_FAILED.value, "the checkout is gone")
    assert _request_state(store, "ask") is RequestState.OPEN


def test_a_missing_amoeba_script_ends_the_row_start_failed_with_its_text(
    tmp_path: Path, store: Store
) -> None:
    def missing() -> Path:
        raise AmoebaScriptMissing("no amoeba script at /x; run uv tool install")

    rig = wake_rig(tmp_path, script=missing)

    result = send_request(store, rig, "ask")

    assert result.outcome is SendOutcome.SENT
    assert rig.spawner.calls == []
    ((_, outcome, detail),) = _wakes(store)
    assert outcome == WakeOutcome.START_FAILED.value
    assert detail == "no amoeba script at /x; run uv tool install"
    assert _request_state(store, "ask") is RequestState.OPEN


def test_no_message_text_reaches_the_wrapper(store: Store, rig: WakeRig) -> None:
    send_request(store, rig, "ask", subject=MARKER_SUBJECT, body=MARKER_BODY)

    (call,) = rig.spawner.calls
    everything = " ".join(
        [*call.argv, str(call.cwd), str(call.logs.stdout), str(call.logs.stderr)]
    )
    assert MARKER_SUBJECT not in everything
    assert MARKER_BODY not in everything
    assert RECIPIENT_NAME not in call.argv


# --- the limit and the retry (6.5) -----------------------------------------------


def _sends_at_each_hour(store: Store, rig: WakeRig, count: int) -> None:
    """A request an hour apart, each when the previous wake's deadline has passed."""
    for index in range(count):
        at(rig, NOW + index * CHAIN_WAIT)
        send_request(store, rig, f"ask-{index}")


def test_the_limit_stops_the_wake_and_the_request_waits_in_the_inbox(
    store: Store, rig: WakeRig
) -> None:
    _sends_at_each_hour(store, rig, MAX_WAKES)
    at(rig, NOW + MAX_WAKES * CHAIN_WAIT)

    result = send_request(store, rig, "over-the-limit")

    assert result.outcome is SendOutcome.SENT
    assert len(rig.spawner.calls) == MAX_WAKES
    assert len(_wakes(store)) == MAX_WAKES
    assert _request_state(store, "over-the-limit") is RequestState.OPEN
    waiting = inbox_of(store, rig, RECIPIENT_NAME)
    assert "over-the-limit" in {view.id for view in waiting.requests}


def test_past_the_ttl_the_sweep_expires_a_request_the_limit_left_and_the_sender_hears(
    store: Store, rig: WakeRig
) -> None:
    _sends_at_each_hour(store, rig, MAX_WAKES)
    at(rig, NOW + MAX_WAKES * CHAIN_WAIT)
    send_request(store, rig, "over-the-limit")
    config = wake_config()
    at(rig, rig.clock.now + timedelta(hours=config.request_open_ttl_hours) + TICK)

    assert sweep_messages(store, config, rig.clock.now) is None
    heard = inbox_of(store, rig, SENDER_NAME, since=0)

    expired = {view.id: view.state for view in heard.requests}
    assert expired["over-the-limit"] is RequestState.EXPIRED
    events = {(item.message_id, item.event) for item in heard.deliveries}
    assert ("over-the-limit", DeliveryEvent.EXPIRED) in events


def test_a_day_and_a_tick_after_the_oldest_counted_row_the_next_send_wakes(
    store: Store, rig: WakeRig
) -> None:
    _sends_at_each_hour(store, rig, MAX_WAKES)
    at(rig, NOW + MAX_WAKES * CHAIN_WAIT)
    send_request(store, rig, "blocked")
    assert len(rig.spawner.calls) == MAX_WAKES

    at(rig, NOW + WAKE_WINDOW + TICK)
    send_request(store, rig, "after-a-day")

    assert len(rig.spawner.calls) == MAX_WAKES + 1


def test_failed_starts_use_the_limit_and_the_next_send_spawns_no_wrapper(
    tmp_path: Path, store: Store
) -> None:
    error = LaunchError(LaunchFailure.SPAWN_ERROR, "cannot start")
    rig = wake_rig(tmp_path, results=[error])

    _sends_at_each_hour(store, rig, MAX_WAKES)
    at(rig, NOW + MAX_WAKES * CHAIN_WAIT)
    send_request(store, rig, "after-the-failures")

    assert len(rig.spawner.calls) == MAX_WAKES
    assert [outcome for _, outcome, _ in _wakes(store)] == [
        WakeOutcome.START_FAILED.value
    ] * MAX_WAKES


def test_a_same_id_retry_of_an_open_request_wakes_again_after_a_start_failure(
    tmp_path: Path, store: Store
) -> None:
    error = LaunchError(LaunchFailure.SPAWN_ERROR, "cannot start")
    rig = wake_rig(tmp_path, results=[error, FakeChild(None)])
    send_request(store, rig, "ask")
    # A wake claimed at the mark's own time is that mark's wake (262 D8): the retry
    # must come later than the failed claim to want a new one.
    at(rig, NOW + TICK)

    retried = send_request(store, rig, "ask")

    assert retried.outcome is SendOutcome.UNCHANGED
    assert len(rig.spawner.calls) == 2
    assert [outcome for _, outcome, _ in _wakes(store)] == [
        WakeOutcome.START_FAILED.value,
        None,
    ]


def test_a_same_id_retry_starts_nothing_while_a_wake_is_live(
    store: Store, rig: WakeRig
) -> None:
    send_request(store, rig, "ask")

    retried = send_request(store, rig, "ask")

    assert retried.outcome is SendOutcome.UNCHANGED
    assert len(rig.spawner.calls) == 1


def test_a_same_id_retry_of_an_accepted_request_starts_nothing(
    store: Store, rig: WakeRig
) -> None:
    send_request(store, rig, "ask")
    accept(store, rig, "ask", RECIPIENT_NAME)
    at(rig, NOW + CHAIN_WAIT)

    retried = send_request(store, rig, "ask")

    assert retried.outcome is SendOutcome.UNCHANGED
    assert retried.request is not None
    assert retried.request.state is RequestState.ACCEPTED
    assert len(rig.spawner.calls) == 1


# --- store behaviour and failures (6.6) ------------------------------------------


class _TransactionCounts:
    """Counts the transactions begun on the store while the wake step runs."""

    def __init__(self, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
        self.reads = 0
        self.writes = 0
        real_step = wake_module.wake_after_send

        def counted_step(step_store: Store, *args: Any) -> Any:
            real_read, real_write = step_store.read, step_store.write
            monkeypatch.setattr(step_store, "read", self._counting(real_read, "reads"))
            monkeypatch.setattr(
                step_store, "write", self._counting(real_write, "writes")
            )
            try:
                return real_step(step_store, *args)
            finally:
                monkeypatch.setattr(step_store, "read", real_read)
                monkeypatch.setattr(step_store, "write", real_write)

        monkeypatch.setattr(wake_module, "wake_after_send", counted_step)

    def _counting(self, real: Any, attribute: str) -> Any:
        def begin() -> Any:
            setattr(self, attribute, getattr(self, attribute) + 1)
            return real()

        return begin


def test_a_recipient_with_no_command_reads_once_and_takes_no_write_lock(
    store: Store, rig: WakeRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    give_command(store, RECIPIENT, None)
    counts = _TransactionCounts(store, monkeypatch)

    send_request(store, rig, "ask")

    # The command is on a checkout now (261 D9), so even "no command" is found by the
    # one pre-check read, never by a write.
    assert (counts.reads, counts.writes) == (1, 0)


def test_a_failed_pre_check_reads_once_and_never_takes_the_write_lock(
    store: Store, rig: WakeRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    send_request(store, rig, "first")  # a live wake now blocks the next
    counts = _TransactionCounts(store, monkeypatch)

    send_request(store, rig, "second")

    assert (counts.reads, counts.writes) == (1, 0)


def test_a_passing_pre_check_reads_once_and_claims_in_one_write(
    store: Store, rig: WakeRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    counts = _TransactionCounts(store, monkeypatch)

    send_request(store, rig, "ask")

    assert (counts.reads, counts.writes) == (1, 1)


def test_a_store_error_in_the_claim_is_returned_and_the_request_stays_written(
    store: Store, rig: WakeRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(*_: Any) -> Any:
        raise StoreBusyError("the store is held")

    monkeypatch.setattr(wake_module, "claim_wake", failing)

    result = send_request(store, rig, "ask")

    assert result.outcome is SendOutcome.SENT
    assert result.wake_problem is not None
    assert "StoreBusyError" in result.wake_problem
    assert RECIPIENT in result.wake_problem
    assert _request_state(store, "ask") is RequestState.OPEN
    assert rig.spawner.calls == []


def test_a_store_error_recording_a_start_failure_leaves_the_row_unended(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = LaunchError(LaunchFailure.SPAWN_ERROR, "cannot start")
    rig = wake_rig(tmp_path, results=[error])

    def failing(*_: Any) -> Any:
        raise StoreBusyError("the store is held")

    monkeypatch.setattr(wake_module, "finish_wake", failing)

    result = send_request(store, rig, "ask")

    assert result.outcome is SendOutcome.SENT
    assert result.wake_problem is not None
    ((wake_id, outcome, _),) = _wakes(store)
    assert outcome is None
    assert _request_state(store, "ask") is RequestState.OPEN
    # The row is the stated exit (D5): running until its deadline, then overdue.
    with store.read() as transaction:
        now = rig.clock.now
        before = wake_summary(transaction, RECIPIENT, now)
        after = wake_summary(transaction, RECIPIENT, now + timedelta(days=1))
    assert before.unended is not None
    assert before.unended.wake_id == wake_id
    assert (before.overdue, after.overdue) == (False, True)


def test_the_wake_step_makes_no_cf_call(store: Store, tmp_path: Path) -> None:
    rig = wake_rig(tmp_path)
    cf_before = len(getattr(rig.deps.cf_run, "calls", []))
    send_request(store, rig, "ask")
    calls_with_wake = len(getattr(rig.deps.cf_run, "calls", [])) - cf_before

    give_command(store, RECIPIENT, None)
    cf_before = len(getattr(rig.deps.cf_run, "calls", []))
    send_request(store, rig, "ask-again")
    calls_without = len(getattr(rig.deps.cf_run, "calls", [])) - cf_before

    assert calls_with_wake == calls_without


def test_the_started_wrapper_is_waited_on_so_it_never_lingers_as_a_zombie(
    tmp_path: Path, store: Store
) -> None:
    waited = threading.Event()

    class _Child(FakeChild):
        def wait(self, timeout: float | None = None) -> int:
            waited.set()
            return 0

    rig = wake_rig(tmp_path, results=[_Child(None)])

    send_request(store, rig, "ask")

    assert waited.wait(timeout=10)
