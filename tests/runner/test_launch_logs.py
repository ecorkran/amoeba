"""Launch log naming, the exact-line confirmation and the bounded tail."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.runner.launch import (
    LAUNCH_LOGS_DIRNAME,
    STDERR_HEAD_LIMIT_BYTES,
    STDERR_TAIL_LIMIT_BYTES,
    log_paths,
    stderr_confirms,
    stderr_tail,
)

RUN_ID = "amoeba-20261023T101500Z-0123456789ab"


def _log(tmp_path: Path, content: bytes) -> Path:
    path = tmp_path / "x.stderr.log"
    path.write_bytes(content)
    return path


def test_logs_are_named_by_entry_id_under_the_launch_logs_directory(
    tmp_path: Path,
) -> None:
    logs = log_paths(tmp_path, "entry-1")

    assert logs.stdout == tmp_path / LAUNCH_LOGS_DIRNAME / "entry-1.stdout.log"
    assert logs.stderr == tmp_path / LAUNCH_LOGS_DIRNAME / "entry-1.stderr.log"


@pytest.mark.parametrize(
    "terminator", [b"\n", b"\r\n", b""], ids=["lf", "crlf", "none"]
)
def test_an_exact_line_confirms(tmp_path: Path, terminator: bytes) -> None:
    content = b"banner\nrun_id=" + RUN_ID.encode() + terminator
    assert stderr_confirms(_log(tmp_path, content), RUN_ID)


@pytest.mark.parametrize(
    "content",
    [
        b"note: run_id=%s started\n",
        b"run_id=%sx\n",
        b" run_id=%s\n",
        b"run_id=other-id\n",
        b"",
        b"run_id=%s\x0bmore\n",
        b"run_id=%s\r\r\n",
    ],
    ids=[
        "inside-line",
        "longer-id",
        "indented",
        "different-id",
        "empty",
        "vertical-tab",
        "double-cr",
    ],
)
def test_anything_but_the_whole_line_does_not_confirm(
    tmp_path: Path, content: bytes
) -> None:
    body = content % RUN_ID.encode() if b"%s" in content else content
    assert not stderr_confirms(_log(tmp_path, body), RUN_ID)


def test_a_line_past_the_head_limit_is_not_seen(tmp_path: Path) -> None:
    filler = b"x" * STDERR_HEAD_LIMIT_BYTES + b"\n"
    content = filler + b"run_id=" + RUN_ID.encode() + b"\n"

    assert not stderr_confirms(_log(tmp_path, content), RUN_ID)


def test_the_tail_is_bounded_to_the_last_bytes(tmp_path: Path) -> None:
    content = b"a" * 10_000 + b"END"

    tail = stderr_tail(_log(tmp_path, content))

    assert len(tail) == STDERR_TAIL_LIMIT_BYTES
    assert tail.endswith("END")


def test_a_short_file_is_returned_whole_and_an_empty_one_is_empty(
    tmp_path: Path,
) -> None:
    assert stderr_tail(_log(tmp_path, b"boom\n")) == "boom\n"
    assert stderr_tail(_log(tmp_path, b"")) == ""


def test_undecodable_bytes_are_replaced_in_the_tail(tmp_path: Path) -> None:
    assert "�" in stderr_tail(_log(tmp_path, b"ok \xff\xfe"))


def test_a_missing_file_raises_os_error(tmp_path: Path) -> None:
    missing = tmp_path / "gone.stderr.log"
    with pytest.raises(OSError):
        stderr_confirms(missing, RUN_ID)
    with pytest.raises(OSError):
        stderr_tail(missing)
