"""The program envelope: parsed from the file format ``submit_program`` writes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from program_harness import member, member_payload, program_payload

from amoeba.inbox.envelope import EnvelopeError
from amoeba.inbox.program_envelope import (
    build_program_envelope,
    parse_program_envelope,
)
from amoeba.store.inbox_models import QuarantineReason
from amoeba.store.program_models import ProgramSubmissionKind

SUBMITTED_AT = datetime(2026, 11, 5, 9, 30, tzinfo=UTC)


def _file_content(
    kind: ProgramSubmissionKind,
    payload: dict[str, object],
    overrides: dict[str, Any] | None = None,
) -> str:
    """What ``submit_program`` writes: the validated envelope, as JSON."""
    envelope = build_program_envelope(
        submission_id="sub-1",
        kind=kind,
        submitted_by="operator",
        submitted_at=SUBMITTED_AT,
        payload=payload,
    )
    data = json.loads(envelope.model_dump_json())
    data.update(overrides or {})
    return json.dumps(data)


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        (ProgramSubmissionKind.REGISTER_PROGRAM, program_payload()),
        (ProgramSubmissionKind.REGISTER_MEMBER, member_payload(member("ui"))),
    ],
)
def test_a_valid_envelope_of_each_kind_parses(
    kind: ProgramSubmissionKind, payload: dict[str, object]
) -> None:
    parsed = parse_program_envelope(_file_content(kind, payload))

    assert parsed.kind is kind
    assert parsed.id == "sub-1"
    assert parsed.submitted_by == "operator"
    assert parsed.submitted_at == SUBMITTED_AT
    assert parsed.payload == json.loads(json.dumps(payload))


def test_the_envelope_carries_no_project_id() -> None:
    content = _file_content(ProgramSubmissionKind.REGISTER_PROGRAM, program_payload())

    assert "project_id" not in {key for key in json.loads(content) if key != "payload"}


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("not json {", QuarantineReason.UNPARSEABLE_ENVELOPE),
        ("[1, 2]", QuarantineReason.UNPARSEABLE_ENVELOPE),
        (
            json.dumps({"envelope_version": 1, "kind": "register_program"}),
            QuarantineReason.UNPARSEABLE_ENVELOPE,
        ),
    ],
)
def test_an_unparseable_file_is_quarantined_as_such(
    content: str, reason: QuarantineReason
) -> None:
    with pytest.raises(EnvelopeError) as caught:
        parse_program_envelope(content)

    assert caught.value.reason is reason


def test_an_unknown_envelope_version_is_named() -> None:
    content = _file_content(
        ProgramSubmissionKind.REGISTER_PROGRAM,
        program_payload(),
        {"envelope_version": 2},
    )

    with pytest.raises(EnvelopeError) as caught:
        parse_program_envelope(content)

    assert caught.value.reason is QuarantineReason.UNKNOWN_ENVELOPE_VERSION


def test_an_unknown_kind_is_named() -> None:
    content = _file_content(
        ProgramSubmissionKind.REGISTER_PROGRAM,
        program_payload(),
        {"kind": "remove_member"},
    )

    with pytest.raises(EnvelopeError) as caught:
        parse_program_envelope(content)

    assert caught.value.reason is QuarantineReason.UNKNOWN_KIND


def test_a_project_kind_sent_to_the_program_parser_is_unknown_kind() -> None:
    content = json.dumps(
        {
            "envelope_version": 1,
            "id": "sub-1",
            "project_id": "demo",
            "kind": "create_project",
            "submitted_by": "operator",
            "submitted_at": SUBMITTED_AT.isoformat(),
            "payload": {},
        }
    )

    with pytest.raises(EnvelopeError) as caught:
        parse_program_envelope(content)

    assert caught.value.reason is QuarantineReason.UNKNOWN_KIND


def test_an_invalid_payload_detail_names_the_offending_field() -> None:
    good = _file_content(
        ProgramSubmissionKind.REGISTER_MEMBER, member_payload(member("ui"))
    )
    data = json.loads(good)
    del data["payload"]["member"]["requests_initiative"]

    with pytest.raises(EnvelopeError) as caught:
        parse_program_envelope(json.dumps(data))

    assert caught.value.reason is QuarantineReason.INVALID_PAYLOAD
    assert "requests_initiative" in caught.value.detail


def test_building_refuses_an_invalid_payload_before_anything_is_written() -> None:
    with pytest.raises(EnvelopeError) as caught:
        build_program_envelope(
            submission_id="sub-1",
            kind=ProgramSubmissionKind.REGISTER_PROGRAM,
            submitted_by="operator",
            submitted_at=SUBMITTED_AT,
            payload={"program_id": "demo"},
        )

    assert caught.value.reason is QuarantineReason.INVALID_PAYLOAD
    assert "concept_member" in caught.value.detail


def test_an_id_that_could_escape_the_inbox_is_unparseable() -> None:
    content = _file_content(
        ProgramSubmissionKind.REGISTER_PROGRAM, program_payload(), {"id": "../escape"}
    )

    with pytest.raises(EnvelopeError) as caught:
        parse_program_envelope(content)

    assert caught.value.reason is QuarantineReason.UNPARSEABLE_ENVELOPE
