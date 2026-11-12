"""The calls log (slice 228, D11): line shapes, bounds, failures and ``last_call``."""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from amoeba.operations.calls_log import (
    CallEntry,
    append_call,
    day_file,
    error_entry,
    last_calls,
    result_entry,
)
from amoeba.upstream.squadron.launch import STDERR_TAIL_LIMIT_BYTES

NOW = datetime(2026, 11, 12, 9, 30, tzinfo=UTC)
DIRECTORY = Path("/work/checkout")


def _lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def test_a_result_line_has_the_result_shape(tmp_path: Path) -> None:
    entry = result_entry("run-a", DIRECTORY, "skipped", "not_paused", None, NOW)

    append_call(tmp_path, entry, NOW)

    (line,) = _lines(day_file(tmp_path, NOW))
    assert list(line) == ["at", "run_id", "directory", "outcome", "reason", "detail"]
    assert line["run_id"] == "run-a"
    assert line["directory"] == str(DIRECTORY)
    assert line["outcome"] == "skipped"
    assert line["reason"] == "not_paused"
    assert line["detail"] is None


def test_an_error_line_has_the_error_shape(tmp_path: Path) -> None:
    entry = error_entry("run-a", DIRECTORY, ValueError("no key"), NOW)

    append_call(tmp_path, entry, NOW)

    (line,) = _lines(day_file(tmp_path, NOW))
    assert list(line) == ["at", "run_id", "directory", "error", "detail"]
    assert line["error"] == "ValueError"
    assert line["detail"] == "no key"


def test_the_day_file_is_named_by_the_utc_date(tmp_path: Path) -> None:
    late = datetime(2026, 11, 12, 23, 0, tzinfo=UTC)

    assert day_file(tmp_path, late).name == "2026-11-12.jsonl"


def test_a_long_detail_is_bounded(tmp_path: Path) -> None:
    long_text = "x" * (STDERR_TAIL_LIMIT_BYTES * 3)
    entry = result_entry("run-a", DIRECTORY, "refused", None, long_text, NOW)

    append_call(tmp_path, entry, NOW)

    (line,) = _lines(day_file(tmp_path, NOW))
    assert isinstance(line["detail"], str)
    assert len(line["detail"].encode("utf-8")) == STDERR_TAIL_LIMIT_BYTES


def test_the_directory_and_its_parents_are_created(tmp_path: Path) -> None:
    log_dir = tmp_path / "state" / "logs" / "calls"
    entry = result_entry("run-a", DIRECTORY, "skipped", None, None, NOW)

    append_call(log_dir, entry, NOW)

    assert day_file(log_dir, NOW).is_file()


def test_a_write_that_fails_gives_one_stderr_line_and_no_exception(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "calls"
    blocker.write_text("a file where the directory should be", encoding="utf-8")
    entry = result_entry("run-a", DIRECTORY, "skipped", None, None, NOW)

    append_call(blocker, entry, NOW)

    error_lines = capsys.readouterr().err.splitlines()
    assert len(error_lines) == 1
    assert "calls log" in error_lines[0]


def test_concurrent_appends_interleave_whole_lines(tmp_path: Path) -> None:
    def append_many(label: str) -> None:
        for number in range(40):
            entry = result_entry(
                f"{label}-{number}", DIRECTORY, "skipped", None, "d" * 200, NOW
            )
            append_call(tmp_path, entry, NOW)

    threads = [threading.Thread(target=append_many, args=(name,)) for name in "abc"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    lines = _lines(day_file(tmp_path, NOW))
    assert len(lines) == 120
    assert {str(line["run_id"]).split("-")[0] for line in lines} == {"a", "b", "c"}


def _log(log_dir: Path, run_id: str, moment: datetime, outcome: str) -> None:
    entry = result_entry(run_id, DIRECTORY, outcome, None, None, moment)
    append_call(log_dir, entry, moment)


class _Found(NamedTuple):
    entry: CallEntry | None
    problems: tuple[str, ...]


def _last_call(log_dir: Path, run_id: str) -> _Found:
    found = last_calls(log_dir, [run_id])
    return _Found(found.entries.get(run_id), found.problems)


def test_last_call_is_the_newest_line_for_the_run_across_day_files(
    tmp_path: Path,
) -> None:
    yesterday = NOW - timedelta(days=1)
    _log(tmp_path, "run-a", yesterday, "skipped")
    _log(tmp_path, "run-b", NOW, "resumed")
    _log(tmp_path, "run-a", NOW, "refused")
    _log(tmp_path, "run-a", NOW + timedelta(minutes=1), "waiting_on_pm")

    found = _last_call(tmp_path, "run-a")

    assert isinstance(found.entry, CallEntry)
    assert found.entry.outcome == "waiting_on_pm"
    assert found.problems == ()


def test_last_call_reads_an_older_day_file_when_the_newer_has_no_line(
    tmp_path: Path,
) -> None:
    _log(tmp_path, "run-a", NOW - timedelta(days=2), "skipped")
    _log(tmp_path, "run-b", NOW, "resumed")

    found = _last_call(tmp_path, "run-a")

    assert found.entry is not None
    assert found.entry.outcome == "skipped"


def test_last_call_is_none_for_an_unknown_run_and_for_no_log(tmp_path: Path) -> None:
    _log(tmp_path, "run-a", NOW, "skipped")

    assert _last_call(tmp_path, "run-z").entry is None
    missing = _last_call(tmp_path / "never-written", "run-a")
    assert missing.entry is None
    assert missing.problems == ()


def test_last_call_skips_a_truncated_line_and_names_it(tmp_path: Path) -> None:
    _log(tmp_path, "run-a", NOW, "skipped")
    path = day_file(tmp_path, NOW)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"at": "2026-11-12T09:31:00Z", "run_id": "run-a", "dir')

    found = _last_call(tmp_path, "run-a")

    assert found.entry is not None
    assert found.entry.outcome == "skipped"
    assert len(found.problems) == 1
    assert f"{path} line 2" in found.problems[0]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_last_call_skips_an_unreadable_file_and_names_it(tmp_path: Path) -> None:
    _log(tmp_path, "run-a", NOW - timedelta(days=1), "skipped")
    newer = day_file(tmp_path, NOW)
    newer.write_text("", encoding="utf-8")
    newer.chmod(0)
    try:
        found = _last_call(tmp_path, "run-a")
    finally:
        newer.chmod(0o600)

    assert found.entry is not None
    assert found.entry.outcome == "skipped"
    assert len(found.problems) == 1
    assert str(newer) in found.problems[0]


def test_last_call_never_raises_on_a_file_that_is_not_utf8(tmp_path: Path) -> None:
    path = day_file(tmp_path, NOW)
    path.write_bytes(b"\xff\xfe not text\n")

    found = _last_call(tmp_path, "run-a")

    assert found.entry is None
    assert len(found.problems) == 1


def test_last_calls_reads_each_file_once_for_many_runs_and_stops_when_all_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _log(tmp_path, "run-a", NOW - timedelta(days=1), "skipped")
    _log(tmp_path, "run-b", NOW, "resumed")
    _log(tmp_path, "run-c", NOW - timedelta(days=5), "skipped")
    reads: list[str] = []
    original = Path.read_text

    def counting_read(self: Path, *arguments: Any, **keywords: Any) -> str:
        reads.append(self.name)
        return original(self, *arguments, **keywords)

    monkeypatch.setattr(Path, "read_text", counting_read)

    found = last_calls(tmp_path, ["run-a", "run-b"])

    assert {run: entry.outcome for run, entry in found.entries.items()} == {
        "run-a": "skipped",
        "run-b": "resumed",
    }
    assert len(reads) == 2  # today's and yesterday's file; the older one is not read


def test_a_short_write_gives_one_stderr_line(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def short_write(descriptor: int, data: bytes) -> int:
        return len(data) - 1

    monkeypatch.setattr(os, "write", short_write)
    entry = result_entry("run-a", DIRECTORY, "skipped", None, None, NOW)

    append_call(tmp_path, entry, NOW)

    assert "short write" in capsys.readouterr().err
