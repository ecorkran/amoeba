"""The four request models, their limits and the views (slice 240, D2, D4, D7, D12)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from store.message_support import (
    ADDRESSEE,
    NOW,
    SENDER,
    TTL,
    seed_members,
    send_request,
)
from store_open import open_local_store

from amoeba.operations.message_models import (
    MAX_BODY_LENGTH,
    MAX_ID_LENGTH,
    MAX_REASON_LENGTH,
    MAX_RESULT_LENGTH,
    MAX_SUBJECT_LENGTH,
    CancelRequest,
    InboxRequest,
    ReplyAction,
    ReplyRequest,
    SendRequest,
)
from amoeba.operations.message_results import (
    DeliveryView,
    RequestDirection,
    RequestView,
)
from amoeba.operations.release_fields import MAX_VERSION_LENGTH
from amoeba.store.deliveries import deliveries_since, write_delivery
from amoeba.store.errors import StoreRowError
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState

HASH = "ab12" * 10


def _send(**fields: Any) -> SendRequest:
    document: dict[str, Any] = {
        "id": "ask-1",
        "to": "other",
        "subject": "a subject",
        "body": "a body",
    }
    return SendRequest.model_validate({**document, **fields})


def _reply(**fields: Any) -> ReplyRequest:
    document: dict[str, Any] = {"id": "ask-1", "action": "accept"}
    return ReplyRequest.model_validate({**document, **fields})


@pytest.mark.parametrize(
    "request_id", ["a", "A9", "a" * MAX_ID_LENGTH, "x.y_z-1", "9lives"]
)
def test_an_id_the_pattern_allows_is_accepted(request_id: str) -> None:
    assert _send(id=request_id).id == request_id


@pytest.mark.parametrize(
    "request_id", [".hidden", "-dash", "_under", "has space", "slash/er", "", " a"]
)
def test_an_id_the_pattern_refuses_is_refused(request_id: str) -> None:
    with pytest.raises(ValidationError):
        _send(id=request_id)


def test_an_id_one_over_the_limit_is_refused_naming_the_limit() -> None:
    with pytest.raises(ValidationError, match=str(MAX_ID_LENGTH)):
        _send(id="a" * (MAX_ID_LENGTH + 1))


def test_a_missing_id_is_refused() -> None:
    with pytest.raises(ValidationError, match="id"):
        SendRequest.model_validate({"to": "o", "subject": "s", "body": "b"})


def test_a_parent_follows_the_same_id_rule() -> None:
    assert _send(parent="p.1").parent == "p.1"
    with pytest.raises(ValidationError, match="parent"):
        _send(parent=".p")


@pytest.mark.parametrize(
    ("field", "limit"),
    [("subject", MAX_SUBJECT_LENGTH), ("body", MAX_BODY_LENGTH)],
)
def test_a_send_text_accepts_the_limit_and_refuses_one_over_naming_it(
    field: str, limit: int
) -> None:
    assert len(getattr(_send(**{field: "x" * limit}), field)) == limit
    with pytest.raises(ValidationError, match=str(limit)):
        _send(**{field: "x" * (limit + 1)})


def test_a_reply_text_accepts_the_limit_and_refuses_one_over_naming_it() -> None:
    text = "x" * MAX_RESULT_LENGTH
    assert _reply(action="done", text=text).text == text
    with pytest.raises(ValidationError, match=str(MAX_RESULT_LENGTH)):
        _reply(action="decline", text=text + "x")


def test_a_cancel_reason_accepts_the_limit_and_refuses_one_over_naming_it() -> None:
    reason = "x" * MAX_REASON_LENGTH
    assert CancelRequest(id="r", reason=reason, member=None).reason == reason
    with pytest.raises(ValidationError, match=str(MAX_REASON_LENGTH)):
        CancelRequest(id="r", reason=reason + "x", member=None)


def test_a_version_over_its_limit_is_refused_naming_it() -> None:
    with pytest.raises(ValidationError, match=str(MAX_VERSION_LENGTH)):
        _reply(action="done", text="t", version="v" * (MAX_VERSION_LENGTH + 1))


@pytest.mark.parametrize("action", [ReplyAction.DECLINE, ReplyAction.DONE])
def test_decline_and_done_need_text(action: ReplyAction) -> None:
    with pytest.raises(ValidationError, match="text is required"):
        _reply(action=action.value)


def test_accept_needs_no_text_and_refuses_one() -> None:
    assert _reply().text is None
    with pytest.raises(ValidationError, match="text is not allowed for accept"):
        _reply(text="why")


@pytest.mark.parametrize("action", [ReplyAction.ACCEPT, ReplyAction.DECLINE])
@pytest.mark.parametrize("field", ["commit", "version"])
def test_commit_and_version_are_only_for_done(action: ReplyAction, field: str) -> None:
    value = HASH if field == "commit" else "v1.0.0"
    extra = {} if action is ReplyAction.ACCEPT else {"text": "no"}
    with pytest.raises(ValidationError, match=f"{field} is only allowed for done"):
        _reply(action=action.value, **extra, **{field: value})


def test_done_takes_a_full_lower_cased_commit_and_a_version() -> None:
    request = _reply(
        action="done", text="shipped", commit=HASH.upper(), version="v1.2.3"
    )

    assert (request.commit, request.version) == (HASH, "v1.2.3")


def test_an_abbreviated_commit_is_refused() -> None:
    with pytest.raises(ValidationError, match="full commit hash"):
        _reply(action="done", text="t", commit="ab12cd3")


def test_a_version_with_whitespace_inside_is_refused() -> None:
    with pytest.raises(ValidationError, match="tag name"):
        _reply(action="done", text="t", version="v 1")


def test_an_unknown_action_is_refused() -> None:
    with pytest.raises(ValidationError, match="action"):
        _reply(action="reopen")


@pytest.mark.parametrize(
    "build",
    [
        lambda: _send(extra="x"),
        lambda: _reply(extra="x"),
        lambda: InboxRequest.model_validate({"extra": "x"}),
        lambda: CancelRequest.model_validate({"id": "r", "extra": "x"}),
    ],
)
def test_an_unknown_field_is_refused(build: Any) -> None:
    with pytest.raises(ValidationError, match="extra"):
        build()


def test_the_requests_are_frozen() -> None:
    with pytest.raises(ValidationError):
        _send().subject = "changed"  # pyright: ignore[reportAttributeAccessIssue]


def test_inbox_since_is_an_integer_of_at_least_zero() -> None:
    assert InboxRequest().since is None
    assert InboxRequest(since=0, member=None).since == 0
    for bad in (-1, "3", 1.5):
        with pytest.raises(ValidationError, match="since"):
            InboxRequest.model_validate({"since": bad})


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, ADDRESSEE)
        yield opened


def test_a_request_view_carries_every_field_and_the_stored_state(
    store: Store,
) -> None:
    with store.write() as transaction:
        message = send_request(transaction, "child", parent_id="root", parent_depth=1)

    view = RequestView.from_message(message, NOW, RequestDirection.RECEIVED)

    assert view.model_dump() == {
        "id": "child",
        "direction": RequestDirection.RECEIVED,
        "from_member": SENDER,
        "to_member": ADDRESSEE,
        "parent_id": "root",
        "depth": 2,
        "subject": "subject of child",
        "body": "body of child",
        "state": RequestState.OPEN,
        "result": None,
        "result_commit": None,
        "result_version": None,
        "reason": None,
        "created_at": NOW,
        "accepted_at": None,
        "state_changed_at": NOW,
        "expires_at": NOW + TTL,
    }


def test_a_request_view_shows_an_unswept_expiry_as_expired(store: Store) -> None:
    with store.write() as transaction:
        message = send_request(transaction, "late")

    view = RequestView.from_message(message, NOW + TTL, RequestDirection.SENT)

    assert view.state is RequestState.EXPIRED
    assert message.state is RequestState.OPEN


def test_a_request_view_carries_a_finished_requests_result(store: Store) -> None:
    with store.write() as transaction:
        message = send_request(transaction, "work")
    finished = replace(
        message,
        state=RequestState.DONE,
        result="shipped",
        result_commit=HASH,
        result_version="v1",
        accepted_at=NOW + timedelta(hours=1),
    )

    view = RequestView.from_message(finished, NOW, RequestDirection.SENT)

    assert view.state is RequestState.DONE
    assert (view.result, view.result_commit, view.result_version) == (
        "shipped",
        HASH,
        "v1",
    )
    assert view.accepted_at == NOW + timedelta(hours=1)


def test_a_note_row_has_no_request_view(store: Store) -> None:
    with store.write() as transaction:
        message = send_request(transaction, "ask")
    note = replace(message, state=None, expires_at=None, to_member=None)

    with pytest.raises(StoreRowError, match="not a request"):
        RequestView.from_message(note, NOW, RequestDirection.SENT)


def test_a_delivery_view_carries_the_delivery(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "ask")
        write_delivery(transaction, ADDRESSEE, "ask", DeliveryEvent.SENT, NOW)
        (delivery,) = deliveries_since(transaction, ADDRESSEE, 0)

    view = DeliveryView.from_delivery(delivery)

    assert view.model_dump() == {
        "seq": delivery.seq,
        "message_id": "ask",
        "event": DeliveryEvent.SENT,
        "created_at": NOW,
    }
