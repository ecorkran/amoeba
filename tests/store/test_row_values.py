"""Typed column reads raise on anything unexpected rather than defaulting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from amoeba.store.errors import StoreRowError
from amoeba.store.row_values import (
    decode_mapping,
    decode_string_list,
    decode_timestamp,
    encode_string_list,
    encode_timestamp,
    integer,
    text,
    vocabulary,
)
from amoeba.store.vocabulary import ConsumedMode


def test_string_list_round_trips_to_a_tuple() -> None:
    assert decode_string_list(encode_string_list(("a", "b")), "col") == ("a", "b")
    assert decode_string_list("[]", "col") == ()


@pytest.mark.parametrize("stored", ["{}", "[1]", "not json", None, 3])
def test_bad_string_list_raises_naming_the_column(stored: object) -> None:
    with pytest.raises(StoreRowError, match="rules_paths"):
        decode_string_list(stored, "rules_paths")


def test_mapping_decodes_an_object_and_refuses_an_array() -> None:
    assert decode_mapping('{"a": 1}', "col") == {"a": 1}
    with pytest.raises(StoreRowError):
        decode_mapping("[1]", "col")


def test_timestamp_round_trips_in_utc() -> None:
    moment = datetime(2026, 11, 9, 12, tzinfo=timezone(timedelta(hours=-5)))

    stored = encode_timestamp(moment)

    assert stored.endswith("+00:00")
    assert decode_timestamp(stored, "col") == moment.astimezone(UTC)


def test_timestamp_without_a_zone_is_refused_both_ways() -> None:
    with pytest.raises(ValueError):
        encode_timestamp(datetime(2026, 11, 9))
    with pytest.raises(StoreRowError):
        decode_timestamp("2026-11-09T12:00:00", "col")
    with pytest.raises(StoreRowError):
        decode_timestamp("yesterday", "col")


def test_scalar_and_vocabulary_reads() -> None:
    assert text("x", "col") == "x"
    assert integer(3, "col") == 3
    assert vocabulary("from_source", ConsumedMode, "col") is ConsumedMode.FROM_SOURCE
    with pytest.raises(StoreRowError):
        integer(True, "col")
    with pytest.raises(StoreRowError, match="ConsumedMode"):
        vocabulary("sometimes", ConsumedMode, "col")
