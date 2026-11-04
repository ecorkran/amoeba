"""``read_reply`` returns a typed reply or a named problem (slice 180 D7).

Fixtures are the D7 JSON written as files, the format the parser consumes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amoeba.runner.request_run.pipeline_file import REPLY_FILE
from amoeba.runner.request_run.reply import (
    AlreadyMet,
    NewSlice,
    ProblemKind,
    ReplyProblem,
    read_reply,
)

FULL_HASH = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


def _write(directory: Path, content: object) -> None:
    text = content if isinstance(content, str) else json.dumps(content)
    (directory / REPLY_FILE).write_text(text, encoding="utf-8")


def _problem(directory: Path) -> ReplyProblem:
    result = read_reply(directory)
    assert isinstance(result, ReplyProblem)
    assert result.detail
    return result


def test_valid_new_slice(tmp_path: Path) -> None:
    _write(tmp_path, {"kind": "new_slice", "index": 91})
    assert read_reply(tmp_path) == NewSlice(index=91)


def test_valid_already_met(tmp_path: Path) -> None:
    _write(tmp_path, {"kind": "already_met", "commit": FULL_HASH})
    assert read_reply(tmp_path) == AlreadyMet(commit=FULL_HASH)


@pytest.mark.parametrize("kind", ["NEW_SLICE", "  new_slice\n", "New_Slice"])
def test_kind_is_trimmed_and_case_insensitive(tmp_path: Path, kind: str) -> None:
    _write(tmp_path, {"kind": kind, "index": 3})
    assert read_reply(tmp_path) == NewSlice(index=3)


def test_unknown_keys_are_ignored(tmp_path: Path) -> None:
    _write(tmp_path, {"kind": "new_slice", "index": 4, "note": "x", "commit": "zz"})
    assert read_reply(tmp_path) == NewSlice(index=4)


@pytest.mark.parametrize("index", [7, "7", " 007 ", "\t12\n"])
def test_index_as_integer_or_padded_digits(tmp_path: Path, index: object) -> None:
    _write(tmp_path, {"kind": "new_slice", "index": index})
    result = read_reply(tmp_path)
    assert isinstance(result, NewSlice)
    assert result.index == int(str(index).strip())


@pytest.mark.parametrize("commit", [FULL_HASH[:7], FULL_HASH, f"  {FULL_HASH}\n"])
def test_commit_of_7_to_40_characters(tmp_path: Path, commit: str) -> None:
    _write(tmp_path, {"kind": "already_met", "commit": commit})
    assert read_reply(tmp_path) == AlreadyMet(commit=commit.strip())


def test_commit_is_normalized_to_lower_case(tmp_path: Path) -> None:
    _write(tmp_path, {"kind": "already_met", "commit": FULL_HASH.upper()})
    assert read_reply(tmp_path) == AlreadyMet(commit=FULL_HASH)


def test_missing_file(tmp_path: Path) -> None:
    assert _problem(tmp_path).kind is ProblemKind.MISSING


def test_absent_directory_is_a_programming_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        read_reply(tmp_path / "absent")


def test_a_file_is_not_a_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "plain.txt"
    file_path.write_text("x")
    with pytest.raises(ValueError, match="does not exist"):
        read_reply(file_path)


def test_reply_file_that_is_a_directory_is_malformed(tmp_path: Path) -> None:
    (tmp_path / REPLY_FILE).mkdir()
    assert _problem(tmp_path).kind is ProblemKind.MALFORMED


def test_invalid_utf8_is_malformed(tmp_path: Path) -> None:
    (tmp_path / REPLY_FILE).write_bytes(
        b'{"kind": "new_slice", "index": 1, "x": "\xff"}'
    )
    assert _problem(tmp_path).kind is ProblemKind.MALFORMED


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json at all",
        [{"kind": "new_slice", "index": 1}],
        {"index": 1},
        {"kind": "maybe", "index": 1},
        {"kind": 3},
        {"kind": "new_slice"},
        {"kind": "new_slice", "index": 0},
        {"kind": "new_slice", "index": -2},
        {"kind": "new_slice", "index": True},
        {"kind": "new_slice", "index": 1.5},
        {"kind": "new_slice", "index": 2.0},
        {"kind": "new_slice", "index": "abc"},
        {"kind": "new_slice", "index": "1.5"},
        {"kind": "new_slice", "index": "-1"},
        {"kind": "new_slice", "index": None},
        {"kind": "already_met"},
        {"kind": "already_met", "commit": FULL_HASH[:6]},
        {"kind": "already_met", "commit": FULL_HASH + "0"},
        {"kind": "already_met", "commit": "g" * 12},
        {"kind": "already_met", "commit": 1234567},
        {"kind": "already_met", "index": 4},
    ],
)
def test_malformed_replies_name_a_cause(tmp_path: Path, content: object) -> None:
    _write(tmp_path, content)
    assert _problem(tmp_path).kind is ProblemKind.MALFORMED
