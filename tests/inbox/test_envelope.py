"""The envelope's kind table, its key pin to the store, and validation order."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from amoeba.inbox.envelope import (
    ENVELOPE_VERSION,
    KIND_PAYLOAD_MODELS,
    EnvelopeError,
    build_envelope,
    parse_envelope,
    validate_envelope,
)
from amoeba.inbox.evidence_payloads import FindingPayload
from amoeba.store.inbox_models import (
    INTENT_BODY,
    INTENT_NODE_ID,
    RESOLUTION_BLOCKED_STATE_ID,
    RESOLUTION_DETAIL,
    QuarantineReason,
    SubmissionKind,
)
from amoeba.store.verdict_payload import FINDING_PAYLOAD_KEYS, VERDICT_PAYLOAD_KEYS

#: The keys each kind's store effect reads, from their single definition. The
#: payload models' field names must equal these exactly.
EFFECT_KEYS = {
    SubmissionKind.CREATE_PROJECT: set[str](),
    SubmissionKind.RESOLUTION: {RESOLUTION_BLOCKED_STATE_ID, RESOLUTION_DETAIL},
    SubmissionKind.INTENT: {INTENT_NODE_ID, INTENT_BODY},
    SubmissionKind.VERDICT: set(VERDICT_PAYLOAD_KEYS),
}


def test_finding_payload_fields_are_the_keys_the_store_reads() -> None:
    assert set(FindingPayload.model_fields) == FINDING_PAYLOAD_KEYS


def _valid() -> dict[str, object]:
    return {
        "envelope_version": ENVELOPE_VERSION,
        "id": "sub-1",
        "project_id": "demo",
        "kind": SubmissionKind.INTENT.value,
        "submitted_by": "tester",
        "submitted_at": "2026-09-23T12:00:00+00:00",
        "payload": {INTENT_BODY: {"want": "x"}},
    }


def _reason(data: dict[str, object]) -> QuarantineReason:
    with pytest.raises(EnvelopeError) as caught:
        validate_envelope(data)
    return caught.value.reason


def test_every_kind_has_a_payload_model() -> None:
    """Adding a kind without its payload model fails here."""
    assert set(KIND_PAYLOAD_MODELS) == set(SubmissionKind)


@pytest.mark.parametrize("kind", list(SubmissionKind))
def test_payload_fields_are_the_keys_the_store_reads(kind: SubmissionKind) -> None:
    assert set(KIND_PAYLOAD_MODELS[kind].model_fields) == EFFECT_KEYS[kind]


def test_a_valid_envelope_parses() -> None:
    envelope = validate_envelope(_valid())

    assert envelope.kind is SubmissionKind.INTENT
    assert envelope.payload == {INTENT_NODE_ID: None, INTENT_BODY: {"want": "x"}}


def test_unknown_extra_fields_are_ignored() -> None:
    data = _valid() | {"from_the_future": True}
    data["payload"] = {INTENT_BODY: {}, "also_ignored": 1}

    envelope = validate_envelope(data)

    assert envelope.payload == {INTENT_NODE_ID: None, INTENT_BODY: {}}


@pytest.mark.parametrize("version", [None, 2, "1", True, 1.0])
def test_anything_but_version_one_is_an_unknown_version(version: object) -> None:
    """``True`` and ``1.0`` compare equal to 1 and must still be refused."""
    assert _reason(_valid() | {"envelope_version": version}) is (
        QuarantineReason.UNKNOWN_ENVELOPE_VERSION
    )


@pytest.mark.parametrize("kind", ["not_a_kind", None, {}, ["intent"]])
def test_an_unknown_or_unhashable_kind_is_named(kind: object) -> None:
    assert _reason(_valid() | {"kind": kind}) is QuarantineReason.UNKNOWN_KIND


@pytest.mark.parametrize(
    "change",
    [
        {"submitted_by": None},
        {"submitted_at": "2026-09-23T12:00:00"},  # naive: no timezone
        {"payload": "not an object"},
        {"id": "../escape"},
    ],
)
def test_a_malformed_envelope_is_unparseable(change: dict[str, object]) -> None:
    assert _reason(_valid() | change) is QuarantineReason.UNPARSEABLE_ENVELOPE


@pytest.mark.parametrize("project_id", ["", "a/b", ".", ".."])
def test_an_unsafe_project_id_is_invalid(project_id: str) -> None:
    assert _reason(_valid() | {"project_id": project_id}) is (
        QuarantineReason.INVALID_PROJECT_ID
    )


def test_a_payload_that_does_not_fit_its_kind_is_invalid() -> None:
    data = _valid() | {"kind": SubmissionKind.RESOLUTION.value}

    assert _reason(data) is QuarantineReason.INVALID_PAYLOAD


@pytest.mark.parametrize("raw", [b"", b"{truncated", b"[1, 2]", b"\xff\xfe"])
def test_content_that_is_not_a_json_object_is_unparseable(raw: bytes) -> None:
    with pytest.raises(EnvelopeError) as caught:
        parse_envelope(raw)

    assert caught.value.reason is QuarantineReason.UNPARSEABLE_ENVELOPE


def test_build_envelope_validates_through_the_same_path() -> None:
    with pytest.raises(EnvelopeError) as caught:
        build_envelope(
            submission_id="sub-1",
            project_id="a/b",
            kind=SubmissionKind.CREATE_PROJECT,
            submitted_by="tester",
            submitted_at=datetime(2026, 9, 23, tzinfo=UTC),
            payload={},
        )

    assert caught.value.reason is QuarantineReason.INVALID_PROJECT_ID
