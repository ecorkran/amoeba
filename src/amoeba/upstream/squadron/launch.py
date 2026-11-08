"""Run ids and the detached launch of ``sq run``."""

from __future__ import annotations

import re
import subprocess
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.run_outcome import SQ_EXECUTABLE

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


#: ``sq run`` prints this, followed by the run id, as a whole stderr line before
#: its first step. It is the one stderr prose is read.
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


def stderr_confirms(path: Path, run_id: str) -> bool:
    """Whether a whole line of the stderr log equals ``run_id=<run_id>``.

    Reads at most :data:`STDERR_HEAD_LIMIT_BYTES`. Before comparing, one
    trailing carriage return and any trailing spaces or tabs are removed, so
    the id inside another line, or a longer id with this one as its prefix,
    does not confirm.

    Raises:
        OSError: If the log cannot be read; the caller decides what that means.
    """
    with path.open("rb") as handle:
        head = handle.read(STDERR_HEAD_LIMIT_BYTES)
    expected = f"{RUN_ID_LINE_PREFIX}{run_id}".encode()
    # Split on b"\n" only: str.splitlines() would also split on form feeds and
    # Unicode separators, which are not terminators. Then drop one trailing b"\r"
    # and any trailing spaces or tabs; a second b"\r" still fails to match.
    return any(
        line.removesuffix(b"\r").rstrip(b" \t") == expected
        for line in head.split(b"\n")
    )


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


#: The ``sq`` subcommand that starts a run, and its flags.
SQ_RUN_COMMAND: Final = "run"
SQ_RUN_ID_FLAG: Final = "--run-id"
SQ_PARAM_FLAG: Final = "-p"

#: Characters Squadron splits or parses on in a ``-p key=value`` argument.
PARAM_VALUE_SEPARATOR: Final = ","
PARAM_KEY_VALUE_SEPARATOR: Final = "="


class ChildHandle(Protocol):
    """The part of a ``subprocess.Popen`` the callers use."""

    def poll(self) -> int | None:
        """The exit code, or ``None`` while the child runs."""
        ...


#: Starts a child. ``subprocess.Popen`` in production, a fake in unit tests.
type PopenFactory = Callable[..., ChildHandle]


@dataclass(frozen=True)
class LaunchError:
    """A launch that did not start a child. ``detail`` names the cause."""

    failure: LaunchFailure
    detail: str


#: Squadron takes a pipeline's primary required parameter as a positional target
#: (``sq run P4 131``) and rejects it as ``-p slice=131`` ("Pipeline 'p4' requires a
#: 'slice' argument"; observed squadron-ai 0.23.7, 20261024). Every dispatched pipeline
#: (P4, P5, P6) has ``slice`` as that parameter, so a ``slice`` parameter is
#: passed positionally and the others as ``-p``.
TARGET_PARAM_KEY: Final = "slice"


def build_argv(
    pipeline: str,
    run_id: str,
    params: Mapping[str, str],
    *,
    target_key: str = TARGET_PARAM_KEY,
) -> list[str]:
    """The ``sq run`` command line: the target, then a ``-p key=value`` per other param.

    ``target_key`` names the param passed positionally: the pipeline's first
    ``required`` param (``slice`` for the dispatched pipelines, ``answer-model`` for
    the answering pipeline).

    Raises:
        ValueError: If a value contains ``,`` or a key contains ``,`` or ``=``
            (Squadron would split them), or the target looks like an option. Call
            this before starting the run.
    """
    argv = [SQ_EXECUTABLE, SQ_RUN_COMMAND, pipeline]
    target = params.get(target_key)
    if target is not None:
        if not target or target.startswith("-"):
            raise ValueError(f"the target {target!r} is not a usable argument")
        argv.append(target)
    argv += [SQ_RUN_ID_FLAG, run_id]
    for key, value in params.items():
        if key == target_key:
            continue
        if problem := param_problem(key, value):
            raise ValueError(problem)
        argv += [SQ_PARAM_FLAG, f"{key}{PARAM_KEY_VALUE_SEPARATOR}{value}"]
    return argv


def param_problem(key: str, value: str) -> str | None:
    """Why Squadron would split this ``-p`` parameter, or ``None`` if it would not."""
    if PARAM_VALUE_SEPARATOR in key or PARAM_KEY_VALUE_SEPARATOR in key:
        return f"parameter key {key!r} may not contain ',' or '='"
    if PARAM_VALUE_SEPARATOR in value:
        return f"parameter {key!r} has a value containing ','"
    return None


def spawn(
    argv: Sequence[str], checkout: str, logs: LaunchLogs, popen: PopenFactory
) -> ChildHandle | LaunchError:
    """Start ``argv`` in ``checkout``, detached, logging to ``logs``.

    Logs are created exclusively, so earlier evidence is never overwritten. The
    child gets its own session, no stdin and the inherited environment (never
    logged); the parent's log handles are closed on return.

    Returns:
        The child handle, or ``spawn_error`` when a log cannot be created or the
        child cannot be started.
    """
    try:
        with ExitStack() as stack:
            stdout = stack.enter_context(logs.stdout.open("xb"))
            stderr = stack.enter_context(logs.stderr.open("xb"))
            return popen(
                argv,
                cwd=checkout,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                close_fds=True,
            )
    except OSError as error:
        # An expected external failure (log creation, missing sq, gone checkout)
        # is an answer for the caller to record, not a bug.
        return LaunchError(
            LaunchFailure.SPAWN_ERROR, f"{type(error).__name__}: {error}"
        )
