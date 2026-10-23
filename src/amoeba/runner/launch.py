"""Run ids and the detached launch of ``sq run``."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

#: Squadron's run id rule: letters, digits, ``.``, ``_`` and ``-``, a letter or
#: digit first, at most 128 characters.
SQUADRON_RUN_ID_PATTERN: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

#: What every Amoeba-minted run id starts with, so it is recognizable in
#: ``sq runs list``.
RUN_ID_PREFIX: Final = "amoeba-"

#: The timestamp part of a minted id.
RUN_ID_TIMESTAMP_FORMAT: Final = "%Y%m%dT%H%M%SZ"

#: How many hex characters of a ``uuid4`` a minted id carries.
RUN_ID_RANDOM_HEX_LENGTH: Final = 12


def mint_run_id(now: datetime) -> str:
    """Return ``amoeba-<UTC timestamp>-<random hex>`` for a launch at ``now``.

    Sortable by time and unique per call. ``now`` must be timezone-aware; it is
    converted to UTC. The pattern is checked by tests, not at runtime.
    """
    stamp = now.astimezone(UTC).strftime(RUN_ID_TIMESTAMP_FORMAT)
    suffix = uuid.uuid4().hex[:RUN_ID_RANDOM_HEX_LENGTH]
    return f"{RUN_ID_PREFIX}{stamp}-{suffix}"


#: The directory under the supervisor directory holding every launch's logs.
LAUNCH_LOGS_DIRNAME: Final = "launch-logs"

#: A launch's two logs are named by its journal entry id plus these suffixes.
STDOUT_LOG_SUFFIX: Final = ".stdout.log"
STDERR_LOG_SUFFIX: Final = ".stderr.log"

#: ``sq run`` prints this, followed by the run id, as a whole stderr line before
#: its first step. It is the one stderr prose the Runner reads.
RUN_ID_LINE_PREFIX: Final = "run_id="

#: The confirmation line is read from at most this many leading bytes of the
#: stderr log, because Squadron prints it before anything else.
STDERR_HEAD_LIMIT_BYTES: Final = 64 * 1024

#: The stderr tail stored in an escalation is at most this many bytes.
STDERR_TAIL_LIMIT_BYTES: Final = 4 * 1024


@dataclass(frozen=True)
class LaunchLogs:
    """The two log files of one launch."""

    stdout: Path
    stderr: Path


def log_paths(supervisor_dir: Path, entry_id: str) -> LaunchLogs:
    """Name a launch's logs by its journal entry id."""
    directory = supervisor_dir / LAUNCH_LOGS_DIRNAME
    return LaunchLogs(
        stdout=directory / f"{entry_id}{STDOUT_LOG_SUFFIX}",
        stderr=directory / f"{entry_id}{STDERR_LOG_SUFFIX}",
    )


def stderr_confirms(path: Path, run_id: str) -> bool:
    """Whether a whole line of the stderr log equals ``run_id=<run_id>``.

    Reads at most :data:`STDERR_HEAD_LIMIT_BYTES`. Only the line terminator is
    removed before comparing, so the id inside another line, or a longer id
    with this one as its prefix, does not confirm.

    Raises:
        OSError: If the log cannot be read; the caller decides what that means.
    """
    with path.open("rb") as handle:
        head = handle.read(STDERR_HEAD_LIMIT_BYTES)
    expected = f"{RUN_ID_LINE_PREFIX}{run_id}".encode()
    # Split on b"\n" only and drop one trailing b"\r": str.splitlines() would
    # also split on form feeds and Unicode separators, which are not terminators.
    return any(line.removesuffix(b"\r") == expected for line in head.split(b"\n"))


def stderr_tail(path: Path) -> str:
    """The last :data:`STDERR_TAIL_LIMIT_BYTES` of the stderr log, decoded.

    Undecodable bytes are replaced. An empty file gives an empty string.

    Raises:
        OSError: If the log cannot be read.
    """
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - STDERR_TAIL_LIMIT_BYTES))
        tail = handle.read()
    return tail.decode("utf-8", errors="replace")
