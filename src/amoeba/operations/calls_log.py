"""The calls log (slice 228, D11): one JSON line per ``handle_pause`` call.

The CLI appends a line for every ending of ``handle_pause``, so a hook that did nothing
leaves a trace (amoeba#34). ``status`` reads the newest line for a run with
``last_calls``. Day files are named ``<UTC date>.jsonl``; ``prune`` removes old ones.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from amoeba.upstream.bounded_text import cut_to_bound

DAY_FILE_SUFFIX: Final = ".jsonl"
DAY_FORMAT: Final = "%Y-%m-%d"
LOG_FILE_MODE: Final = 0o600
LINE_ENCODING: Final = "utf-8"


class CallEntry(BaseModel):
    """One call: a result (``outcome`` and ``reason``) or an exit-3 ``error``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: datetime
    run_id: str
    #: The call's working directory.
    directory: str
    outcome: str | None = None
    reason: str | None = None
    #: The exception's name, for a call that ended in an error.
    error: str | None = None
    detail: str | None = None

    def to_line(self) -> str:
        """The JSON line: the result shape or the error shape, never a mix."""
        keys = {"at", "run_id", "directory", "detail"}
        keys |= {"error"} if self.error is not None else {"outcome", "reason"}
        return self.model_dump_json(include=keys)


def result_entry(
    run_id: str,
    directory: Path,
    outcome: str,
    reason: str | None,
    detail: str | None,
    now: datetime,
) -> CallEntry:
    """The entry for a call that returned a result."""
    return CallEntry(
        at=now,
        run_id=run_id,
        directory=str(directory),
        outcome=outcome,
        reason=reason,
        detail=detail,
    )


def error_entry(
    run_id: str, directory: Path, error: BaseException, now: datetime
) -> CallEntry:
    """The entry for a call that ended in an exit-3 error."""
    return CallEntry(
        at=now,
        run_id=run_id,
        directory=str(directory),
        error=type(error).__name__,
        detail=str(error),
    )


def day_file(log_dir: Path, moment: datetime) -> Path:
    """The day file holding ``moment`` (its UTC date)."""
    return log_dir / f"{moment.astimezone(UTC).strftime(DAY_FORMAT)}{DAY_FILE_SUFFIX}"


def append_call(log_dir: Path, entry: CallEntry, now: datetime) -> None:
    """Append ``entry`` to today's day file, creating ``log_dir`` and its parents.

    The file is opened with ``O_APPEND`` and the line goes out in one write, so
    concurrent hooks do not interleave. ``detail`` is cut to the shared bound first.
    A failed write puts one line on stderr and returns.
    """
    bounded = entry.model_copy(
        update={"detail": None if entry.detail is None else cut_to_bound(entry.detail)}
    )
    line = (bounded.to_line() + "\n").encode(LINE_ENCODING)
    path = day_file(log_dir, now)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, LOG_FILE_MODE
        )
        try:
            written = os.write(descriptor, line)
            if written != len(line):
                # A second write could interleave with another hook's line.
                raise OSError(f"short write: {written} of {len(line)} bytes")
        finally:
            os.close(descriptor)
    except OSError as error:
        # The log is a trace: failing to write it must not change the call's result
        # or exit code, so the failure is reported on stderr and not raised.
        sys.stderr.write(f"error: calls log: cannot write {path}: {error}\n")


@dataclass(frozen=True)
class LastCalls:
    """``last_calls``' answer: the newest entry per run found, and what it skipped."""

    entries: dict[str, CallEntry]
    #: One text per unreadable day file or bad line met on the way.
    problems: tuple[str, ...]


def last_calls(log_dir: Path, run_ids: Collection[str]) -> LastCalls:
    """The newest line for each of ``run_ids``, reading day files newest first and
    each file once, and stopping when every run has one. Never raises.

    A day file that cannot be read, and a line that is not a valid entry (an
    interrupted append, for example), is skipped and named in ``problems``.
    """
    problems: list[str] = []
    wanted = set(run_ids)
    found: dict[str, CallEntry] = {}
    for path in _day_files_newest_first(log_dir, problems):
        if not wanted:
            break
        for run_id, entry in _newest_per_run(path, wanted, problems).items():
            found[run_id] = entry
            wanted.discard(run_id)
    return LastCalls(found, tuple(problems))


def _day_files_newest_first(log_dir: Path, problems: list[str]) -> list[Path]:
    try:
        names = [
            path for path in log_dir.iterdir() if path.name.endswith(DAY_FILE_SUFFIX)
        ]
    except FileNotFoundError:
        # No calls log yet: nothing has been logged, which is not a problem.
        return []
    except OSError as error:
        problems.append(f"calls log {log_dir}: cannot list: {error}")
        return []
    return sorted(names, key=lambda path: path.name, reverse=True)


def _newest_per_run(
    path: Path, run_ids: set[str], problems: list[str]
) -> dict[str, CallEntry]:
    """The newest entry in the file for each of ``run_ids`` that it holds."""
    try:
        text = path.read_text(encoding=LINE_ENCODING)
    except (OSError, UnicodeDecodeError) as error:
        problems.append(f"calls log {path}: cannot read: {error}")
        return {}
    found: dict[str, CallEntry] = {}
    for number, line in reversed(list(enumerate(text.splitlines(), start=1))):
        if not line.strip():
            continue
        try:
            entry = CallEntry.model_validate_json(line)
        except ValidationError:
            # An interrupted or hand-edited line: skipped and named, not fatal.
            problems.append(f"calls log {path} line {number}: not a valid entry")
            continue
        if entry.run_id in run_ids and entry.run_id not in found:
            found[entry.run_id] = entry
    return found
