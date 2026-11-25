"""The after-step runner: start the work a machine has waiting, off the tick's path
(slice 263, D7).

After every tick that got a reply the session runs 262's after-step with what that
reply said: the file clean-up when due, and ``claim_work`` when the work flag is set.
It runs in its own worker thread, one at a time, and never in the tick's: a slow
``claim_work`` (it retries, up to one call bound) delays neither the next tick nor a
heartbeat. A tick that ends while one is running starts none; the flag is still set in
the next reply, which starts it then. The thread opens its own steps and closes them
when the after-step returns, and never uses the tick's.

No outcome ends presence or changes a tick, and none is retried here: the next tick's
flag is the retry. Failures are logged by the run (one WARNING when a run starts or its
error type changes, one INFO on recovery). A claimed item that fails to start is
recorded by ``start_claimed`` and is not a failure of the after-step.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import replace
from functools import partial
from typing import Any

import anyio
import anyio.to_thread

from amoeba.mcp.presence import FailureLog, PresenceDeps
from amoeba.wiring_presence import (
    AFTER_STEP_ERRORS,
    AmoebaHomeError,
    ConfigError,
    LastReply,
    run_after_step,
)

logger = logging.getLogger(__name__)


class HubFlagProblem(Exception):
    """The hub could not tell whether this machine has work waiting."""


#: What the after-step's thread raises when it cannot finish; the work is found again.
RUN_ERRORS = (
    *AFTER_STEP_ERRORS,
    ConfigError,
    AmoebaHomeError,
    HubFlagProblem,
)

type Spawn = Callable[[Callable[[], Coroutine[Any, Any, None]]], object]


class AfterRunner:
    """Runs the after-step for a tick's reply, one at a time."""

    def __init__(self, deps: PresenceDeps, spawn: Spawn) -> None:
        self._deps = deps
        self._spawn = spawn
        self._running = False
        self._failures = FailureLog("after-step")

    @property
    def running(self) -> bool:
        """Whether an after-step is running now."""
        return self._running

    def start(self, tick_last: LastReply) -> None:
        """Start the after-step for the reply ``tick_last`` came from, unless one is
        still running. Called on the event loop."""
        if self._running:
            return
        self._running = True
        self._spawn(partial(self._run, replace(tick_last)))

    async def _run(self, tick_last: LastReply) -> None:
        try:
            await anyio.to_thread.run_sync(self._body, tick_last)
            self._failures.recovered()
        except RUN_ERRORS as error:
            # No reply or a refusal starts nothing; the next tick's flag is the retry.
            self._failures.failed(error)
        except Exception:
            # The thread's one boundary: log it and free the runner for the next tick.
            logger.exception("the after-step failed unexpectedly")
        finally:
            self._running = False

    def _body(self, tick_last: LastReply) -> None:
        """The after-step in its own thread, on its own steps."""
        if tick_last.problem is not None:
            raise HubFlagProblem(tick_last.problem)
        last = replace(tick_last)
        with self._deps.open_steps(last) as steps:
            run_after_step(steps, self._deps.after_deps, last, prunes=True)
