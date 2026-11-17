"""The note kind of ``SendRequest`` and ``NoteView`` (slice 243, D1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from amoeba.operations.message_models import (
    MAX_BODY_LENGTH,
    MAX_ID_LENGTH,
    MAX_SUBJECT_LENGTH,
    SendRequest,
)
from amoeba.operations.message_results import NoteView
from amoeba.store.models import Message
from amoeba.store.vocabulary import MessageKind

CREATED = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def _document(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"id": "n-id", "subject": "a subject", "body": "a body"}
    return {**base, **fields}


def _note(**fields: Any) -> SendRequest:
    return SendRequest.model_validate(_document(kind="note", **fields))


def _request(**fields: Any) -> SendRequest:
    return SendRequest.model_validate(_document(to="other", **fields))


def test_a_note_with_to_only_validates() -> None:
    note = _note(to="other")
    assert (note.kind, note.to, note.to_program) == (MessageKind.NOTE, "other", None)


def test_a_note_with_to_program_only_validates() -> None:
    note = _note(to_program="prog")
    assert (note.to, note.to_program) == (None, "prog")


@pytest.mark.parametrize(
    "fields",
    [
        {"to": "other", "to_program": "prog"},
        {},
    ],
    ids=["both", "neither"],
)
def test_a_note_needs_exactly_one_recipient_naming_the_fields_and_kind(
    fields: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match=r"to_program.*note"):
        _note(**fields)


def test_a_note_with_a_parent_is_refused_naming_the_field_and_kind() -> None:
    with pytest.raises(ValidationError, match=r"parent.*note"):
        _note(to="other", parent="p-1")


@pytest.mark.parametrize("field", ["subject", "body", "id"])
def test_a_note_without_a_required_text_is_refused_naming_it(field: str) -> None:
    document = _document(kind="note", to="other")
    del document[field]
    with pytest.raises(ValidationError, match=field):
        SendRequest.model_validate(document)


def test_a_request_with_to_program_is_refused_naming_the_field_and_kind() -> None:
    with pytest.raises(ValidationError, match=r"to_program.*request"):
        _request(to_program="prog")


def test_a_request_without_to_is_refused_naming_the_field_and_kind() -> None:
    with pytest.raises(ValidationError, match=r"to is required.*request"):
        SendRequest.model_validate(_document(kind="request"))


def test_a_document_with_no_kind_is_a_request() -> None:
    assert _request().kind is MessageKind.REQUEST
    with pytest.raises(ValidationError, match="request"):
        SendRequest.model_validate(_document(to_program="prog"))


@pytest.mark.parametrize("kind", ["announcement", "", "Note", 1])
def test_a_kind_outside_the_enum_is_refused(kind: object) -> None:
    with pytest.raises(ValidationError, match="kind"):
        SendRequest.model_validate(_document(kind=kind, to="other"))


@pytest.mark.parametrize("kind", [MessageKind.NOTE, MessageKind.REQUEST])
def test_the_text_limits_bind_a_note_as_a_request(kind: MessageKind) -> None:
    fields: dict[str, Any] = {"to": "other", "kind": kind.value}
    at_limit = SendRequest.model_validate(
        _document(
            id="a" * MAX_ID_LENGTH,
            subject="s" * MAX_SUBJECT_LENGTH,
            body="b" * MAX_BODY_LENGTH,
            **fields,
        )
    )
    assert len(at_limit.id) == MAX_ID_LENGTH
    for field, limit in (
        ("id", MAX_ID_LENGTH),
        ("subject", MAX_SUBJECT_LENGTH),
        ("body", MAX_BODY_LENGTH),
    ):
        with pytest.raises(ValidationError, match=str(limit)):
            SendRequest.model_validate(
                _document(**{**fields, field: "x" * (limit + 1)})
            )


def _message(**fields: Any) -> Message:
    values: dict[str, Any] = {
        "message_id": "n-id",
        "kind": MessageKind.NOTE,
        "from_member": "from-m",
        "to_member": "to-m",
        "to_program": None,
        "parent_id": None,
        "depth": 1,
        "subject": "a subject",
        "body": "a body",
        "state": None,
        "result": None,
        "result_commit": None,
        "result_version": None,
        "reason": None,
        "accepted_at": None,
        "created_at": CREATED,
        "state_changed_at": CREATED,
        "expires_at": None,
    }
    return Message(**{**values, **fields})


def test_a_direct_note_view_carries_every_field_with_a_null_program() -> None:
    view = NoteView.from_message(_message())
    assert view.model_dump() == {
        "id": "n-id",
        "from_member": "from-m",
        "to_member": "to-m",
        "to_program": None,
        "subject": "a subject",
        "body": "a body",
        "created_at": CREATED,
    }


def test_a_program_note_view_has_a_null_to_member() -> None:
    view = NoteView.from_message(_message(to_member=None, to_program="prog"))
    assert (view.to_member, view.to_program) == (None, "prog")


def test_a_request_row_is_not_a_note_view() -> None:
    with pytest.raises(ValueError, match="not a note"):
        NoteView.from_message(_message(kind=MessageKind.REQUEST))
