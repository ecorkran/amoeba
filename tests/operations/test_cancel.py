"""``cancel``: who is told, who may cancel, every refusal (slice 240, D3, D4, D5,
D9)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run
from store.message_support import count, delivery_rows

from amoeba.operations.deps import Deps
from amoeba.operations.errors import ContextForgeError
from amoeba.operations.message_models import MAX_REASON_LENGTH, CancelOutcome
from amoeba.operations.message_results import CancelResult, RequestDirection
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from operations.message_placed import cancel
from operations.message_support import (
    CONFIG,
    RECIPIENT,
    RECIPIENT_NAME,
    SENDER,
    end_request,
    message_cf,
    message_deps,
    open_message_store,
    rejection_rows,
    send_note_as_sender,
    send_request_as_sender,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY

TTL = timedelta(hours=CONFIG.request_open_ttl_hours)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from open_message_store(tmp_path)


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def sender_deps(tmp_path: Path, clock: SettableClock) -> Deps:
    """Called from the sender's own directory."""
    return message_deps(tmp_path, clock)


@pytest.fixture
def outside_deps(tmp_path: Path, clock: SettableClock) -> Deps:
    """A session in no member."""
    return message_deps(tmp_path, clock, message_cf(OUTSIDE_ANY_PROJECT))


def _cancel(store: Store, deps: Deps, **fields: Any) -> CancelResult:
    return cancel(
        store, CONFIG, {"id": "ask", **fields}, directory=DIRECTORY, deps=deps
    )


def _state(store: Store, request_id: str = "ask") -> RequestState | None:
    with store.read() as transaction:
        message = get_message(transaction, request_id)
    return None if message is None else message.state


def _deliveries(store: Store) -> list[tuple[int, str, str, str]]:
    with store.read() as transaction:
        return delivery_rows(transaction)


def test_the_senders_cancel_reaches_the_addressee_only(
    store: Store, sender_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _cancel(store, sender_deps, reason="no longer needed")

    assert result.outcome is CancelOutcome.CANCELLED
    assert result.request is not None
    assert result.request.state is RequestState.CANCELLED
    assert result.request.reason == "no longer needed"
    assert result.request.direction is RequestDirection.SENT
    assert result.notice
    assert _deliveries(store) == [
        (1, RECIPIENT, "ask", "sent"),
        (2, RECIPIENT, "ask", "cancelled"),
    ]


def test_a_cancel_from_a_session_in_no_member_reaches_both(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _cancel(store, outside_deps)

    assert result.outcome is CancelOutcome.CANCELLED
    assert result.request is not None
    assert result.request.direction is None
    assert _deliveries(store)[1:] == [
        (2, SENDER, "ask", "cancelled"),
        (3, RECIPIENT, "ask", "cancelled"),
    ]
    assert rejection_rows(store) == []


def test_the_addressee_may_cancel_too(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _cancel(store, outside_deps, member=RECIPIENT_NAME)

    assert result.outcome is CancelOutcome.CANCELLED
    assert result.request is not None
    assert result.request.direction is RequestDirection.RECEIVED
    assert _deliveries(store)[1:] == [(2, SENDER, "ask", "cancelled")]


def test_an_accepted_request_can_be_cancelled(store: Store, sender_deps: Deps) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    with store.write() as transaction:
        message = get_message(transaction, "ask")
        assert message is not None
        change_state(
            transaction,
            message,
            RequestState.ACCEPTED,
            DeliveryEvent.ACCEPTED,
            RECIPIENT,
            sender_deps.clock(),
            StateFields(accepted_at=sender_deps.clock()),
        )

    result = _cancel(store, sender_deps)

    assert result.outcome is CancelOutcome.CANCELLED
    assert _state(store) is RequestState.CANCELLED


def test_a_repeat_names_the_state_the_first_call_reached(
    store: Store, sender_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    _cancel(store, sender_deps)

    result = _cancel(store, sender_deps)

    assert result.rejection is RejectCode.NOT_APPLICABLE
    assert RequestState.CANCELLED.value in result.problems[0]
    assert len(_deliveries(store)) == 2
    assert rejection_rows(store) == [
        (SENDER, "cancel", "-", "ask", "-", "not_applicable")
    ]


@pytest.mark.parametrize("state", [RequestState.DONE, RequestState.DECLINED])
def test_a_finished_request_cannot_be_cancelled(
    store: Store, sender_deps: Deps, state: RequestState
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    end_request(store, "ask", state, sender_deps)

    result = _cancel(store, sender_deps)

    assert result.rejection is RejectCode.NOT_APPLICABLE
    assert state.value in result.problems[0]


def test_an_expired_request_is_not_applicable_naming_expired(
    store: Store, sender_deps: Deps, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    clock.now += TTL

    result = _cancel(store, sender_deps)

    assert result.rejection is RejectCode.NOT_APPLICABLE
    assert RequestState.EXPIRED.value in result.problems[0]
    assert _state(store) is RequestState.EXPIRED


def test_an_unknown_id_is_refused_and_recorded_for_a_known_caller(
    store: Store, sender_deps: Deps
) -> None:
    result = _cancel(store, sender_deps)

    assert result.rejection is RejectCode.UNKNOWN_REQUEST
    assert rejection_rows(store) == [
        (SENDER, "cancel", "-", "ask", "-", "unknown_request")
    ]


def test_an_unknown_caller_leaves_no_row(store: Store, outside_deps: Deps) -> None:
    result = _cancel(store, outside_deps)

    assert result.rejection is RejectCode.UNKNOWN_REQUEST
    assert rejection_rows(store) == []


def test_an_explicit_member_that_is_no_member_is_refused_and_cancels_nothing(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _cancel(store, outside_deps, member="no-such-member")

    assert result.rejection is RejectCode.NOT_A_MEMBER
    assert "no-such-member" in result.problems[0]
    assert _state(store) is RequestState.OPEN
    assert rejection_rows(store) == []


def test_a_member_mismatch_leaves_a_row_under_the_directorys_member(
    store: Store, sender_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _cancel(store, sender_deps, member=RECIPIENT_NAME)

    assert result.rejection is RejectCode.MEMBER_MISMATCH
    assert _state(store) is RequestState.OPEN
    assert rejection_rows(store) == [
        (SENDER, "cancel", "-", "ask", "-", "member_mismatch")
    ]


def test_an_over_long_reason_is_malformed_and_recorded_for_a_known_caller(
    store: Store, sender_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _cancel(store, sender_deps, reason="x" * (MAX_REASON_LENGTH + 1))

    assert result.rejection is RejectCode.MALFORMED
    assert str(MAX_REASON_LENGTH) in result.problems[0]
    assert _state(store) is RequestState.OPEN
    assert rejection_rows(store) == [(SENDER, "cancel", "-", "ask", "-", "malformed")]


def test_a_malformed_cancel_from_an_unknown_caller_leaves_no_row(
    store: Store, outside_deps: Deps
) -> None:
    result = cancel(
        store, CONFIG, {"reason": "no id"}, directory=DIRECTORY, deps=outside_deps
    )

    assert result.rejection is RejectCode.MALFORMED
    assert rejection_rows(store) == []


def test_a_cf_failure_raises_and_writes_nothing(
    store: Store, sender_deps: Deps, tmp_path: Path, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    down = message_deps(tmp_path, clock, fake_cf_run(None))

    with pytest.raises(ContextForgeError):
        _cancel(store, down)

    assert _state(store) is RequestState.OPEN
    with store.read() as transaction:
        assert count(transaction, "message_rejections") == 0


def test_a_notes_id_is_unknown_request_naming_a_note_and_the_note_is_unchanged(
    store: Store, sender_deps: Deps
) -> None:
    send_note_as_sender(store, sender_deps, "a-note")
    with store.read() as transaction:
        before = get_message(transaction, "a-note")

    result = _cancel(store, sender_deps, id="a-note")

    assert result.rejection is RejectCode.UNKNOWN_REQUEST
    assert "note" in result.problems[0]
    with store.read() as transaction:
        assert get_message(transaction, "a-note") == before
        assert count(transaction, "deliveries") == 1
