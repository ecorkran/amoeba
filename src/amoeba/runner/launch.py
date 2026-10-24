"""Run ids and the detached launch of ``sq run``."""

from __future__ import annotations

import re
import subprocess
import uuid
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol, cast

from amoeba.process import SQ_EXECUTABLE
from amoeba.runner.faults import LaunchFailure
from amoeba.store import PARAM_CHECKOUT, PARAM_RUN_ID, JournalEntry

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


#: The ``sq`` subcommand that starts a run, and its flags.
SQ_RUN_COMMAND: Final = "run"
SQ_RUN_ID_FLAG: Final = "--run-id"
SQ_PARAM_FLAG: Final = "-p"

#: Journal parameter keys besides the run id and checkout.
PARAM_PIPELINE: Final = "pipeline"
PARAM_PARAMS: Final = "params"
#: Set on the entry that reissues a launch recovery found never started (D9): the
#: id of the ``not_applied`` entry it repeats.
PARAM_REISSUE_OF: Final = "reissue_of"

#: Characters Squadron splits or parses on in a ``-p key=value`` argument.
PARAM_VALUE_SEPARATOR: Final = ","
PARAM_KEY_VALUE_SEPARATOR: Final = "="


class ChildHandle(Protocol):
    """The part of a ``subprocess.Popen`` the Runner uses."""

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
#: 'slice' argument"; observed squadron-ai 0.23.7, 20261024). Every pipeline the Runner
#: dispatches (P4, P5, P6) has ``slice`` as that parameter, so a ``slice`` parameter is
#: passed positionally and the others as ``-p``.
TARGET_PARAM_KEY: Final = "slice"


def build_argv(pipeline: str, run_id: str, params: Mapping[str, str]) -> list[str]:
    """The ``sq run`` command line: the target, then a ``-p key=value`` per other param.

    Raises:
        ValueError: If a value contains ``,`` or a key contains ``,`` or ``=``
            (Squadron would split them), or the target looks like an option. Call
            this before journaling.
    """
    argv = [SQ_EXECUTABLE, SQ_RUN_COMMAND, pipeline]
    target = params.get(TARGET_PARAM_KEY)
    if target is not None:
        if not target or target.startswith("-"):
            raise ValueError(f"the target {target!r} is not a usable argument")
        argv.append(target)
    argv += [SQ_RUN_ID_FLAG, run_id]
    for key, value in params.items():
        if key == TARGET_PARAM_KEY:
            continue
        if PARAM_VALUE_SEPARATOR in key or PARAM_KEY_VALUE_SEPARATOR in key:
            raise ValueError(f"parameter key {key!r} may not contain ',' or '='")
        if PARAM_VALUE_SEPARATOR in value:
            raise ValueError(f"parameter {key!r} has a value containing ','")
        argv += [SQ_PARAM_FLAG, f"{key}{PARAM_KEY_VALUE_SEPARATOR}{value}"]
    return argv


def _text_parameter(entry: JournalEntry, key: str) -> str:
    value = entry.parameters.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"entry {entry.id} has an unusable {key!r}: {value!r}")
    return value


def _params_parameter(entry: JournalEntry) -> dict[str, str]:
    raw = entry.parameters.get(PARAM_PARAMS)
    if not isinstance(raw, Mapping):
        raise ValueError(f"entry {entry.id} has unusable params: {raw!r}")
    value = cast("Mapping[object, object]", raw)
    params: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"entry {entry.id} has a non-string param: {key!r}")
        params[key] = item
    return params


def launch(
    entry: JournalEntry, supervisor_dir: Path, popen: PopenFactory
) -> ChildHandle | LaunchError:
    """Start ``sq run`` for a journaled entry, detached.

    Both logs are created exclusively, so an earlier attempt's evidence is never
    overwritten. The child gets its own session, no stdin and the inherited
    environment (Squadron's providers read credentials from it); the
    environment is never logged. The parent's log handles are closed on return.

    Raises:
        ValueError: If the entry's parameters are unusable or unlaunchable.

    Returns:
        The child handle, or a ``spawn_error`` answer when a log cannot be
        created or the child cannot be started.
    """
    argv = build_argv(
        _text_parameter(entry, PARAM_PIPELINE),
        _text_parameter(entry, PARAM_RUN_ID),
        _params_parameter(entry),
    )
    checkout = _text_parameter(entry, PARAM_CHECKOUT)
    logs = log_paths(supervisor_dir, entry.id)
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


@dataclass
class TrackedLaunch:
    """A child launched in this lifetime and whether its run is confirmed."""

    child: ChildHandle
    confirmed: bool = False


class LaunchTracker:
    """The children this process launched, so they are reaped and not leaked.

    In memory only. After a restart every in-flight entry has a run state, so it
    needs no handle (D3); the children themselves live in their own sessions.
    """

    def __init__(self) -> None:
        self._launches: dict[str, TrackedLaunch] = {}

    def track(self, entry_id: str, child: ChildHandle) -> None:
        """Remember a freshly launched, unconfirmed child."""
        self._launches[entry_id] = TrackedLaunch(child)

    def get(self, entry_id: str) -> TrackedLaunch | None:
        """The tracked launch for an entry, if this lifetime made one."""
        return self._launches.get(entry_id)

    def confirm(self, entry_id: str) -> None:
        """Mark a launch confirmed (by its line or a run state)."""
        self._launches[entry_id].confirmed = True

    def forget(self, entry_id: str) -> None:
        """Stop tracking an entry whose launch is finished with."""
        self._launches.pop(entry_id, None)

    def reap(self) -> None:
        """Poll every child, collecting exits; drop exited, confirmed ones.

        An exited but unconfirmed child stays: observation still needs its exit
        to decide whether the launch failed.
        """
        for entry_id, tracked in list(self._launches.items()):
            exited = tracked.child.poll() is not None
            if exited and tracked.confirmed:
                del self._launches[entry_id]
