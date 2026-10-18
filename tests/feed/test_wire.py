"""``change_record``: the wire form ``amoeba feed`` prints and the stream sends."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import MappingProxyType

from amoeba.feed.wire import change_record
from amoeba.store import Change
from amoeba.store.feed_models import ChangeKind

_RECORDED_AT = datetime(2026, 10, 17, 12, 30, tzinfo=UTC)

_CHANGE = Change(
    seq=42,
    project_id="demo",
    kind=ChangeKind.MESSAGE_POSTED,
    node_id=None,
    subject_id="message-1",
    payload=MappingProxyType({"channel": "intent"}),
    recorded_at=_RECORDED_AT,
)


def test_keys_are_in_change_field_order() -> None:
    assert list(change_record(_CHANGE)) == [
        "seq",
        "project_id",
        "kind",
        "node_id",
        "subject_id",
        "payload",
        "recorded_at",
    ]


def test_kind_is_the_enum_value() -> None:
    kind = change_record(_CHANGE)["kind"]

    assert kind == "message_posted"
    assert type(kind) is str


def test_recorded_at_is_iso_text() -> None:
    assert change_record(_CHANGE)["recorded_at"] == _RECORDED_AT.isoformat()


def test_payload_is_a_plain_dict() -> None:
    payload = change_record(_CHANGE)["payload"]

    assert type(payload) is dict
    assert payload == {"channel": "intent"}


def test_the_record_serializes_without_a_default_hook() -> None:
    assert json.loads(json.dumps(change_record(_CHANGE)))["seq"] == 42
