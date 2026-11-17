"""``as_request``: the one place an id is told to be a request, a note or nothing
(slice 243, D4)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from amoeba.operations.reject_codes import NotARequest, as_request
from amoeba.store.models import Message
from amoeba.store.vocabulary import MessageKind, RequestState

WHEN = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
REQUEST = Message(
    message_id="ask",
    kind=MessageKind.REQUEST,
    from_member="a",
    to_member="b",
    to_program=None,
    parent_id=None,
    depth=1,
    subject="s",
    body="b",
    state=RequestState.OPEN,
    result=None,
    result_commit=None,
    result_version=None,
    reason=None,
    accepted_at=None,
    created_at=WHEN,
    state_changed_at=WHEN,
    expires_at=WHEN,
)
NOTE = replace(REQUEST, message_id="news", kind=MessageKind.NOTE, state=None)


def test_a_request_is_returned_as_it_is() -> None:
    assert as_request("ask", REQUEST) is REQUEST


def test_a_missing_id_and_a_note_are_each_a_detail() -> None:
    missing = as_request("nothing", None)
    note = as_request("news", NOTE)

    assert isinstance(missing, NotARequest) and "no request" in missing.detail
    assert isinstance(note, NotARequest) and "is a note" in note.detail


def test_a_request_row_with_no_state_is_a_bug_not_a_refusal() -> None:
    with pytest.raises(ValueError, match="no state"):
        as_request("ask", replace(REQUEST, state=None))
