"""The after-step: start the work a machine has waiting (slice 262, D10).

``after_call`` runs once at the end of ``wiring.invoke`` (the CLI door after every
operation, the MCP door after every operation but ``answer``) and at the end of
``amoeba handle-pause``, on every path, a raise included. It runs the file clean-up when
one is due, then, if the last reply said this machine has work waiting, makes one
``claim_work`` call and starts what it returns, detached. It never raises and never
changes the result of the call it follows.

``LastReply`` is the per-command holder of what the last reply said: a door reply's
``work`` flag, or the problem text that stands in for it. With the local steps no reply
carries a flag, so the flag is one read of ``work_waiting``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from amoeba.client.errors import HubRefusedError, HubUnreachableError
from amoeba.config.home import AmoebaHomeError
from amoeba.config.user_config import ConfigError
from amoeba.operations.deps import Deps
from amoeba.operations.names import Door, OperationName
from amoeba.operations.steps.models import CLAIM_WORK, OPEN_RUNS
from amoeba.operations.steps.models_runs import OpenRunsReply, OpenRunsRequest
from amoeba.operations.steps.models_work import ClaimWorkRequest
from amoeba.operations.store_steps import LocalSteps, Steps
from amoeba.operations.work_start import start_claimed
from amoeba.store.errors import StoreError
from amoeba.store.store import BUSY_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

#: One busy timeout per store transaction the after-step makes on the local way: the
#: flag read, ``open_runs`` when a prune is due, and ``claim_work`` (D10). The spawns
#: do not wait. The after-step's one bound (it replaces the held-start step's).
AFTER_STEP_BOUND_SECONDS: Final = 3 * BUSY_TIMEOUT_SECONDS


@dataclass
class LastReply:
    """What the last reply of one command said about waiting work."""

    #: The reply's ``work`` flag; ``None`` when no reply carried one.
    work: bool | None = None
    #: The reply's ``work_problem`` (the hub could not tell), printed once.
    problem: str | None = None
    #: A call got no reply: the hub is not answering, so the after-step makes none.
    unreachable: bool = False


def after_operation(  # noqa: PLR0913 - what the after-step is given
    name: OperationName,
    door: Door,
    steps: Steps | None,
    last: LastReply,
    deps: Callable[[], Deps],
) -> None:
    """The after-step of ``wiring.invoke``: after every operation on the CLI door, and
    on the MCP door after every operation but ``answer``, whose call a deadline bounds
    by its resume alone (``check_deadline``). ``status`` and ``list`` prune in their
    own placement."""
    if door is Door.MCP and name is OperationName.ANSWER:
        return
    prunes = name not in (OperationName.STATUS, OperationName.LIST)
    after_call(steps, deps, last, prunes=prunes)


def after_call(  # noqa: PLR0913 - the pieces of one after-step
    steps: Steps | None,
    deps: Callable[[], Deps],
    last: LastReply,
    *,
    prunes: bool,
) -> None:
    """The after-step. ``steps`` is ``None`` when none can be made (a joined machine
    until its steps are the door's): nothing happens. Never raises."""
    if steps is None or last.unreachable:
        return
    try:
        built = deps()
        if prunes:
            _prune(steps, built)
        if _work_waiting(steps, last):
            reply = steps.run(
                CLAIM_WORK, ClaimWorkRequest(logs_dir=str(built.logs_dir))
            )
            start_claimed(steps, built, reply.items)
    except (ConfigError, AmoebaHomeError) as error:
        # Not re-raised: the call this follows has committed, so raising would report a
        # failure for work that happened. One line and no traceback: a missing or
        # invalid config is the person's to fix, not a crash. The work is found again
        # by the next call.
        logger.error("the after-step stopped; its work is found again: %s", error)
    except (StoreError, HubUnreachableError, HubRefusedError, OSError):
        # Not re-raised, for the reason above. Nothing was started; the claims, if the
        # hub applied them, run out and the work is handed out again (D10, D11).
        logger.exception("the after-step stopped; its work is found again next call")


def _prune(steps: Steps, deps: Deps) -> None:
    """The file clean-up when a walk is due; its problems are a log line here (D12)."""

    def open_runs() -> OpenRunsReply:
        return steps.run(OPEN_RUNS, OpenRunsRequest())

    report = deps.prune(open_runs, now=deps.clock())
    if report.problems:
        logger.error("the clean-up after the call had problems: %s", report.note())


def _work_waiting(steps: Steps, last: LastReply) -> bool:
    """The reply's flag when it carried one; with the local steps, one read."""
    if last.work is not None:
        return last.work
    if isinstance(steps, LocalSteps):
        return steps.work_waiting()
    return False
