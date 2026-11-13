"""Run an in-process tool in a worker thread under a deadline (slice 226, D4, D12).

The server's event loop must never wait on SQLite, ``sq`` or ``cf``, so every
in-process call, the store open included, runs in a worker thread. The call is cut
off after ``MCP_CALL_DEADLINE_SECONDS`` and the caller gets ``CallTimedOut`` with the
tool's advice; the worker is abandoned, finishes on its own and closes its store.
"""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import Final

import anyio
import anyio.to_thread

from amoeba import wiring
from amoeba.mcp.tools import ToolSpec
from amoeba.operations.names import Door, OperationName

logger = logging.getLogger(__name__)

#: The longest any MCP call may take. It must exceed ``wiring.answer_bound_seconds``
#: for a sane config (that is 150.5 s for the config contract's example), so it cannot
#: sit under Codex's default tool timeout of 60 s; the install doc tells Codex users to
#: raise ``tool_timeout_sec`` to at least this plus 5. Claude Code's default is about
#: 28 hours. Checked 20261112 (slice 226, task 0.3).
MCP_CALL_DEADLINE_SECONDS: Final = 180.0


class CallTimedOut(Exception):
    """A tool did not finish within the deadline; the message says what to do next."""


def _invoke_logged(
    name: OperationName, document: object, directory: Path | None
) -> dict[str, object]:
    """``wiring.invoke`` on the MCP door, as the JSON document the CLI prints.

    Runs in a worker thread, so the result is serialized here, not on the event loop.
    A failure is logged before it propagates: after the deadline nobody awaits this
    call's result, so a failure then would be lost.

    ``answer`` first checks the config this call will use against the deadline (D12):
    the start-up check saw the config as it was then, and a person may have raised
    ``resume_wait_seconds`` since. The refusal comes before anything is recorded.

    Raises:
        wiring.DeadlineError: ``answer``'s bound is not below the deadline.
    """
    if name is OperationName.ANSWER:
        wiring.check_deadline(wiring.load_config(), MCP_CALL_DEADLINE_SECONDS)
    try:
        return wiring.result_document(
            wiring.invoke(name, document, directory, Door.MCP)
        )
    except Exception:
        logger.exception("%s failed in its worker thread", name.value)
        raise


async def run_in_process(
    spec: ToolSpec, document: object, directory: Path | None
) -> dict[str, object]:
    """Run ``spec``'s operation and return its result as the JSON the CLI prints.

    Raises:
        CallTimedOut: The call outlived ``MCP_CALL_DEADLINE_SECONDS``.
        wiring.OPERATIONAL_ERRORS: As the operation raises them.
        wiring.DeadlineError: ``answer`` with a config whose bound reaches the deadline.
        ValueError: ``spec`` has no timeout advice (it is not an in-process tool).
    """
    if spec.timeout_advice is None:
        raise ValueError(f"{spec.name.value} is not an in-process tool")
    deadline = MCP_CALL_DEADLINE_SECONDS
    with anyio.move_on_after(deadline):
        return await anyio.to_thread.run_sync(
            partial(_invoke_logged, spec.name, document, directory),
            abandon_on_cancel=True,
        )
    # Reached only when the deadline cancelled the wait: a ``return`` or an error
    # inside the block never gets here. ``move_on_after`` rather than ``fail_after``
    # so a ``TimeoutError`` of the operation itself is never taken for the deadline.
    raise CallTimedOut(
        f"{spec.name.value} did not finish within {deadline:g} s; {spec.timeout_advice}"
    )
