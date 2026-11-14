"""The text helpers: cutting prose, never cutting commands (slice 229, D2, 8.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from amoeba.cli.render.text import (
    COLUMNS,
    ELLIPSIS,
    command_line,
    cut,
    how_long,
    one_line,
    prose_line,
    was_cut,
)


def test_the_width_is_one_hundred() -> None:
    assert COLUMNS == 100


def test_a_short_text_is_unchanged() -> None:
    assert cut("Which file limit?") == "Which file limit?"


def test_a_300_character_question_is_cut_to_exactly_100_columns() -> None:
    cut_text = cut("word " * 60)

    assert len(cut_text) <= COLUMNS
    assert cut_text.endswith(ELLIPSIS)
    assert "\n" not in cut_text


def test_a_text_of_exactly_the_limit_is_not_cut() -> None:
    assert cut("x" * COLUMNS) == "x" * COLUMNS
    assert cut("x" * (COLUMNS + 1)) == "x" * (COLUMNS - 1) + ELLIPSIS


def test_newlines_and_runs_of_blanks_collapse_to_one_line() -> None:
    assert one_line("first\n\n  second\tthird ") == "first second third"
    assert cut("first\nsecond") == "first second"


def test_a_prose_line_with_its_prefix_is_at_most_100_columns() -> None:
    line = prose_line("    question: ", "y" * 300)

    assert len(line) == COLUMNS
    assert line.startswith("    question: ")
    assert line.endswith(ELLIPSIS)


def test_a_command_longer_than_100_columns_is_whole_on_its_own_line() -> None:
    command = "amoeba answer " + "r" * 150 + " --text TEXT"

    line = command_line(command)

    assert line == "    " + command
    assert len(line) > COLUMNS


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(seconds=20), "<1m"),
        (timedelta(minutes=7, seconds=30), "7m"),
        (timedelta(hours=5, minutes=12), "5h 12m"),
        (timedelta(days=3, hours=4, minutes=30), "3d 4h"),
        (timedelta(seconds=-5), "<1m"),
    ],
)
def test_how_long_gives_a_short_age(age: timedelta, expected: str) -> None:
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)

    assert how_long(now - age, now) == expected


def test_was_cut_agrees_with_prose_line() -> None:
    prefix = "    question: "
    for text in ("short", "y" * 85, "y" * 86, "y" * 300):
        line = prose_line(prefix, text)

        assert was_cut(prefix, text) == (line != prefix + text)
