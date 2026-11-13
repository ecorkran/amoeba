"""Start ``handle_pause`` as a detached child of the server (slice 226, D6).

``handle_pause`` can run an answering run for minutes, longer than a client waits for
a tool. So the server starts the ``amoeba`` command itself, in its own session, and
returns a receipt at once. The child is the CLI's ``handle_pause``: it claims the
pause, runs the answering run for at most ``answering_wait_seconds`` and exits, and it
appends the calls-log line the same way a shell run does. Its logs are old files under
``logs/mcp/``, which ``prune`` removes by age.
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Final

import anyio
import anyio.to_thread
from pydantic import BaseModel, ConfigDict, ValidationError

from amoeba import wiring
from amoeba.mcp.tools import RequestError
from amoeba.operations.handle_pause_call import HandlePauseCall
from amoeba.operations.names import OperationName
from amoeba.wiring import LaunchError

AMOEBA_SCRIPT_NAME: Final = "amoeba"
#: Marks the end of options, so a run id that starts with ``-`` is not read as a flag.
END_OF_OPTIONS: Final = "--"
UNIQUE_LENGTH: Final = 8


class AmoebaScriptMissing(Exception):
    """The ``amoeba`` script is not beside the server's interpreter."""


class HandlePauseNotStarted(Exception):
    """The child could not be started; the message is the launch failure's text."""


class StartedCall(BaseModel):
    """The receipt of a detached call: what started and where its result will land."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: OperationName
    pid: int
    cwd: Path
    started_at: datetime
    stdout_log: Path
    stderr_log: Path


def resolve_amoeba_script() -> Path:
    """The ``amoeba`` script installed beside this interpreter.

    ``uv tool install`` puts ``amoeba`` and ``amoeba-mcp`` in one environment, so the
    script is next to ``sys.executable`` (not resolved: a symlinked interpreter would
    lead to another directory).

    Raises:
        AmoebaScriptMissing: There is no such file; the message names the path.
    """
    script = Path(sys.executable).parent / AMOEBA_SCRIPT_NAME
    if not script.exists():
        raise AmoebaScriptMissing(
            f"the amoeba script is not at {script}; install with "
            "`uv tool install --force <repo>` so amoeba and amoeba-mcp share one "
            "environment"
        )
    return script


def _validated(raw: Mapping[str, object] | None) -> HandlePauseCall:
    try:
        return HandlePauseCall.model_validate({} if raw is None else dict(raw))
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
            for problem in error.errors()
        )
        raise RequestError(problems) from error


def _start(script: Path, call: HandlePauseCall) -> StartedCall:
    """Create the logs and start the child; blocking, so it runs in a thread."""
    started_at = datetime.now(UTC)
    logs = wiring.detached_logs(
        OperationName.HANDLE_PAUSE, started_at, uuid.uuid4().hex[:UNIQUE_LENGTH]
    )
    argv = [
        str(script),
        OperationName.HANDLE_PAUSE.value,
        END_OF_OPTIONS,
        call.run_id,
    ]
    # The child's cwd is the run's checkout, which ``handle_pause`` reads as its
    # directory; never the server's own directory.
    child = wiring.start_child(argv, call.directory, logs)
    if isinstance(child, LaunchError):
        raise HandlePauseNotStarted(child.detail)
    return StartedCall(
        operation=OperationName.HANDLE_PAUSE,
        pid=child.pid,
        cwd=call.directory,
        started_at=started_at,
        stdout_log=logs.stdout,
        stderr_log=logs.stderr,
    )


async def start_handle_pause(raw: Mapping[str, object] | None) -> StartedCall:
    """Start ``amoeba handle_pause`` for the run and checkout ``raw`` names.

    Raises:
        RequestError: ``raw`` is not a run id and an absolute directory; nothing
            started.
        AmoebaScriptMissing: The ``amoeba`` script is not installed.
        HandlePauseNotStarted: A log or the child could not be created.
        wiring.OPERATIONAL_ERRORS: The state home cannot be located.
    """
    call = _validated(raw)
    script = resolve_amoeba_script()
    return await anyio.to_thread.run_sync(partial(_start, script, call))
