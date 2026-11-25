"""The channel event: numbers and closed words only (slice 241, D4, 5.2)."""

from __future__ import annotations

import pytest

from amoeba.mcp.channel_event import (
    META_COUNT,
    META_FIRST_SEQ,
    META_LAST_SEQ,
    channel_event,
)
from amoeba.store.models import PushRow
from amoeba.store.vocabulary import DeliveryEvent, MessageKind
from amoeba.wire.protocol import CHANNEL_EVENT_MAX_ENTRIES

#: Planted where message text would be if it leaked; the counterparty is the only
#: free-ish value a row carries, and it is a Context Forge id.
MARKERS = ("MARKER-SUBJECT", "MARKER-BODY", "MARKER-RESULT", "MARKER-REASON")
PEER = "sender-member"


def _row(seq: int, event: DeliveryEvent = DeliveryEvent.SENT) -> PushRow:
    return PushRow(seq=seq, event=event, kind=MessageKind.REQUEST, counterparty=PEER)


def test_no_marker_text_can_reach_the_event() -> None:
    # The function takes no text field at all: the rows have none to give.
    rows = [_row(seq) for seq in range(1, 4)]

    event = channel_event(rows)

    rendered = event["content"] + "".join(event["meta"].values())
    assert not any(marker in rendered for marker in MARKERS)
    assert set(PushRow.__dataclass_fields__) == {"seq", "event", "kind", "counterparty"}


def test_one_row_gives_equal_first_and_last_and_a_count_of_one() -> None:
    event = channel_event([_row(7)])

    assert event["meta"] == {META_FIRST_SEQ: "7", META_LAST_SEQ: "7", META_COUNT: "1"}
    assert "1 new delivery " in event["content"]
    assert "(seq 7-7)" in event["content"]


def test_many_rows_give_the_range_and_the_count() -> None:
    event = channel_event([_row(3), _row(5), _row(9)])

    assert event["meta"] == {META_FIRST_SEQ: "3", META_LAST_SEQ: "9", META_COUNT: "3"}
    assert "3 new deliveries" in event["content"]


def test_one_past_the_cap_lists_the_cap_and_counts_one_more() -> None:
    rows = [_row(seq) for seq in range(1, CHANNEL_EVENT_MAX_ENTRIES + 2)]

    content = channel_event(rows)["content"]

    assert content.count(f"from {PEER}") == CHANNEL_EVENT_MAX_ENTRIES
    assert "and 1 more" in content


def test_every_meta_key_is_an_identifier_and_every_value_digits() -> None:
    meta = channel_event([_row(1), _row(2)])["meta"]

    assert all(key.isidentifier() for key in meta)
    assert all(value.isdigit() for value in meta.values())


def test_a_note_names_its_sender_and_a_request_event_the_other_party() -> None:
    note = PushRow(1, DeliveryEvent.SENT, MessageKind.NOTE, "note-sender")
    accepted = PushRow(2, DeliveryEvent.ACCEPTED, MessageKind.REQUEST, "addressee")

    content = channel_event([note, accepted])["content"]

    assert "note, sent from note-sender" in content
    assert "request, accepted with addressee" in content


def test_the_instruction_points_at_the_callers_own_cursor() -> None:
    content = channel_event([_row(41)])["content"]

    assert "Call the inbox tool" in content
    assert "since=<as_of_seq from your last inbox call>" in content
    assert "omit since if you have none" in content


def test_an_empty_batch_is_a_bug() -> None:
    with pytest.raises(ValueError, match="at least one"):
        channel_event([])
