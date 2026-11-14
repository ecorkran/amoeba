"""``parse_since``: the shared starting-time rule."""

from __future__ import annotations

import pytest

from amoeba.operations.since import parse_since


def test_one_instant_in_three_offset_forms_gives_the_same_text() -> None:
    forms = (
        "2026-11-09T12:00:00+00:00",
        "2026-11-09T12:00:00Z",
        "2026-11-09T07:00:00-05:00",
    )
    assert len({parse_since(form) for form in forms}) == 1


def test_the_text_is_the_stores_utc_form() -> None:
    assert parse_since("2026-11-09T07:00:00-05:00") == "2026-11-09T12:00:00+00:00"


def test_a_time_without_an_offset_is_rejected_with_its_message() -> None:
    value = "2026-11-09T12:00:00"
    with pytest.raises(ValueError) as raised:
        parse_since(value)
    assert str(raised.value) == f"has no UTC offset: {value!r}"


@pytest.mark.parametrize("value", ["garbage", ""])
def test_an_unparseable_time_is_rejected_with_its_message(value: str) -> None:
    with pytest.raises(ValueError) as raised:
        parse_since(value)
    assert str(raised.value) == f"not an ISO-8601 time: {value!r}"


def test_surrounding_whitespace_is_stripped() -> None:
    assert parse_since("  2026-11-09T12:00:00Z \n") == "2026-11-09T12:00:00+00:00"
