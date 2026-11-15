"""``reply``: each D4 transition, every refusal and what is recorded (slice 240, D4,
D5, D9)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run
from store.message_support import count, delivery_rows

from amoeba.operations.deps import Deps
from amoeba.operations.members import ContextForgeError
from amoeba.operations.message_models import ReplyOutcome
from amoeba.operations.message_results import ReplyResult, RequestDirection
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.reply import reply
from amoeba.store.messages import get_message
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import RequestState
from operations.message_support import (
    CONFIG,
    RECIPIENT,
    RECIPIENT_NAME,
    SENDER,
    SENDER_NAME,
    end_request,
    message_cf,
    message_deps,
    open_message_store,
    rejection_rows,
    send_request_as_sender,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY

HASH = "ab12" * 10
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
def addressee_deps(tmp_path: Path, clock: SettableClock) -> Deps:
    """A session in no member: the addressee is named with ``member``."""
    return message_deps(tmp_path, clock, message_cf(OUTSIDE_ANY_PROJECT))


def _reply(
    store: Store, deps: Deps, request_id: str, action: str, **fields: Any
) -> ReplyResult:
    document = {"id": request_id, "action": action, "member": RECIPIENT_NAME, **fields}
    return reply(store, CONFIG, document, directory=DIRECTORY, deps=deps)


def _stored(store: Store, request_id: str) -> Any:
    with store.read() as transaction:
        return get_message(transaction, request_id)


def _deliveries(store: Store) -> list[tuple[int, str, str, str]]:
    with store.read() as transaction:
        return delivery_rows(transaction)


def test_accept_moves_an_open_request_to_accepted_and_tells_the_sender(
    store: Store, sender_deps: Deps, addressee_deps: Deps, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    clock.now += timedelta(hours=1)

    result = _reply(store, addressee_deps, "ask", "accept")

    assert result.outcome is ReplyOutcome.APPLIED
    assert result.rejection is None
    assert result.request is not None
    assert result.request.state is RequestState.ACCEPTED
    assert result.request.direction is RequestDirection.RECEIVED
    assert result.request.accepted_at == clock.now
    assert result.notice
    assert _deliveries(store) == [
        (1, RECIPIENT, "ask", "sent"),
        (2, SENDER, "ask", "accepted"),
    ]


@pytest.mark.parametrize("accept_first", [False, True])
def test_decline_works_from_open_and_from_accepted(
    store: Store, sender_deps: Deps, addressee_deps: Deps, accept_first: bool
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    if accept_first:
        _reply(store, addressee_deps, "ask", "accept")

    result = _reply(store, addressee_deps, "ask", "decline", text="not now")

    assert result.outcome is ReplyOutcome.APPLIED
    stored = _stored(store, "ask")
    assert (stored.state, stored.reason) == (RequestState.DECLINED, "not now")
    assert _deliveries(store)[-1] == (
        3 if accept_first else 2,
        SENDER,
        "ask",
        "declined",
    )


def test_done_stores_the_result_commit_and_version(
    store: Store, sender_deps: Deps, addressee_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    _reply(store, addressee_deps, "ask", "accept")

    result = _reply(
        store, addressee_deps, "ask", "done", text="shipped", commit=HASH, version="v1"
    )

    assert result.outcome is ReplyOutcome.APPLIED
    stored = _stored(store, "ask")
    assert stored.state is RequestState.DONE
    assert (stored.result, stored.result_commit, stored.result_version) == (
        "shipped",
        HASH,
        "v1",
    )
    assert _deliveries(store)[-1] == (3, SENDER, "ask", "done")
    assert rejection_rows(store) == []


def test_an_unknown_request_is_refused_and_recorded(
    store: Store, addressee_deps: Deps
) -> None:
    result = _reply(store, addressee_deps, "nothing", "accept")

    assert result.rejection is RejectCode.UNKNOWN_REQUEST
    assert rejection_rows(store) == [
        (RECIPIENT, "reply", "-", "nothing", "-", "unknown_request")
    ]


def test_only_the_addressee_may_reply(store: Store, sender_deps: Deps) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = reply(
        store,
        CONFIG,
        {"id": "ask", "action": "accept"},
        directory=DIRECTORY,
        deps=sender_deps,
    )

    assert result.rejection is RejectCode.NOT_ADDRESSEE
    assert _stored(store, "ask").state is RequestState.OPEN
    assert rejection_rows(store) == [
        (SENDER, "reply", "-", "ask", "-", "not_addressee")
    ]


def test_a_second_accept_names_when_the_first_happened(
    store: Store, sender_deps: Deps, addressee_deps: Deps, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    clock.now += timedelta(hours=2)
    _reply(store, addressee_deps, "ask", "accept")
    accepted_at = encode_timestamp(clock.now)
    clock.now += timedelta(hours=1)

    result = _reply(store, addressee_deps, "ask", "accept")

    assert result.rejection is RejectCode.ALREADY_ACCEPTED
    assert accepted_at in result.problems[0]
    assert len(_deliveries(store)) == 2


def test_done_on_an_open_request_says_to_accept_first(
    store: Store, sender_deps: Deps, addressee_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _reply(store, addressee_deps, "ask", "done", text="finished")

    assert result.rejection is RejectCode.NOT_APPLICABLE
    assert "accept it first" in result.problems[0]
    assert _stored(store, "ask").state is RequestState.OPEN


@pytest.mark.parametrize(
    "state", [RequestState.DONE, RequestState.DECLINED, RequestState.CANCELLED]
)
@pytest.mark.parametrize("action", ["accept", "decline", "done"])
def test_any_action_on_a_terminal_request_names_its_state(
    store: Store,
    sender_deps: Deps,
    addressee_deps: Deps,
    state: RequestState,
    action: str,
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    end_request(store, "ask", state, sender_deps)
    fields = {} if action == "accept" else {"text": "text"}

    result = _reply(store, addressee_deps, "ask", action, **fields)

    assert result.rejection is RejectCode.NOT_APPLICABLE
    assert state.value in result.problems[0]
    assert _stored(store, "ask").state is state


def test_a_request_past_its_ttl_is_not_applicable_naming_expired(
    store: Store, sender_deps: Deps, addressee_deps: Deps, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    clock.now += TTL

    result = _reply(store, addressee_deps, "ask", "accept")

    assert result.rejection is RejectCode.NOT_APPLICABLE
    assert RequestState.EXPIRED.value in result.problems[0]
    assert _stored(store, "ask").state is RequestState.EXPIRED
    assert _deliveries(store)[-2:] == [
        (2, SENDER, "ask", "expired"),
        (3, RECIPIENT, "ask", "expired"),
    ]


def test_a_rejected_reply_leaves_one_row_under_the_caller(
    store: Store, sender_deps: Deps, addressee_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    _reply(store, addressee_deps, "ask", "accept")

    _reply(store, addressee_deps, "ask", "accept")

    assert rejection_rows(store) == [
        (RECIPIENT, "reply", "-", "ask", "-", "already_accepted")
    ]


def test_a_member_mismatch_leaves_a_row_under_the_directorys_member(
    store: Store, sender_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = reply(
        store,
        CONFIG,
        {"id": "ask", "action": "accept", "member": RECIPIENT_NAME},
        directory=DIRECTORY,
        deps=sender_deps,
    )

    assert result.rejection is RejectCode.MEMBER_MISMATCH
    assert _stored(store, "ask").state is RequestState.OPEN
    assert rejection_rows(store) == [
        (SENDER, "reply", "-", "ask", "-", "member_mismatch")
    ]


def test_a_malformed_reply_is_recorded_and_changes_nothing(
    store: Store, sender_deps: Deps, addressee_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _reply(store, addressee_deps, "ask", "decline")

    assert result.rejection is RejectCode.MALFORMED
    assert "text is required" in result.problems[0]
    assert _stored(store, "ask").state is RequestState.OPEN
    assert rejection_rows(store) == [(RECIPIENT, "reply", "-", "ask", "-", "malformed")]


def test_not_a_member_writes_no_row(store: Store, addressee_deps: Deps) -> None:
    result = reply(
        store,
        CONFIG,
        {"id": "ask", "action": "accept"},
        directory=DIRECTORY,
        deps=addressee_deps,
    )

    assert result.rejection is RejectCode.NOT_A_MEMBER
    assert rejection_rows(store) == []


def test_a_cf_failure_raises_and_writes_nothing(
    store: Store, sender_deps: Deps, tmp_path: Path, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    down = message_deps(tmp_path, clock, fake_cf_run(None))

    with pytest.raises(ContextForgeError):
        _reply(store, down, "ask", "accept")

    assert _stored(store, "ask").state is RequestState.OPEN
    with store.read() as transaction:
        assert count(transaction, "message_rejections") == 0


def test_a_reply_makes_at_most_two_cf_lookups(
    store: Store, sender_deps: Deps, tmp_path: Path, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    cf = message_cf(OUTSIDE_ANY_PROJECT)

    _reply(store, message_deps(tmp_path, clock, cf), "ask", "accept")

    assert len(cf.calls) == 2


def test_the_sender_name_is_not_needed_to_reply(
    store: Store, sender_deps: Deps, addressee_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _reply(store, addressee_deps, "ask", "accept")

    assert result.request is not None
    assert result.request.from_member == SENDER
    assert SENDER_NAME not in result.request.subject
