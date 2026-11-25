"""The after-step: start the work a machine has waiting (slice 262, D10).

``after_call`` runs once at the end of ``wiring.invoke`` on the CLI door (the MCP door
leaves it to the session's tick, 263 D7) and at the end of
``amoeba handle-pause``, on every path, a raise included. It runs the file clean-up when
one is due, then, if the last reply said this machine has work waiting, makes one
``claim_work`` call and starts what it returns, detached. It never raises and never
changes the result of the call it follows.

``LastReply`` is the per-command holder of what the last reply said: a door reply's
``work`` flag, or the problem text that stands in for it. With the local steps no reply
carries a flag, so the flag is one read of ``work_waiting``.

``DoorSteps`` sends each step as one door call (D3); ``steps_for`` picks it or
``LocalSteps`` once per command, by whether a client file exists.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from pydantic import ValidationError

from amoeba.client.call import call
from amoeba.client.client_file import load_client_file
from amoeba.client.errors import (
    ClientFileError,
    HubCertificateError,
    HubRefusedError,
    HubUnreachableError,
)
from amoeba.config.home import (
    AmoebaHomeError,
    StateLayout,
    client_file_path,
    pinned_cert_path,
)
from amoeba.config.user_config import ConfigError, UserConfig
from amoeba.operations import list_view
from amoeba.operations.deps import Deps
from amoeba.operations.names import OperationName
from amoeba.operations.state_move import open_state_store
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.models import CLAIM_WORK, OPEN_RUNS, Step, StepModel
from amoeba.operations.steps.models_runs import OpenRunsReply, OpenRunsRequest
from amoeba.operations.steps.models_work import ClaimWorkRequest
from amoeba.operations.store_steps import LocalSteps, Steps
from amoeba.operations.work_start import start_claimed
from amoeba.store.errors import StoreError
from amoeba.store.store import BUSY_TIMEOUT_SECONDS
from amoeba.wire.protocol import WORK_PROBLEM_REPLY_KEY, WORK_REPLY_KEY
from amoeba.wire.times import DoorTimes

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


def take_work_keys(result: dict[str, object], last: LastReply) -> None:
    """Move a done reply's ``work`` and ``work_problem`` out of its result document
    into ``last``, so the result rebuilds as the local way's and the after-step reads
    them."""
    work = result.pop(WORK_REPLY_KEY, None)
    problem = result.pop(WORK_PROBLEM_REPLY_KEY, None)
    if isinstance(work, bool):
        last.work = work
    if isinstance(problem, str):
        last.problem = problem


class StepReplyError(Exception):
    """A done reply that does not fit the step's reply model (D11): the two sides
    disagree inside one door version, which is a bug. Raised on the client."""


class DoorSteps:
    """Each step as one door call: the request model as the ``document`` of
    ``POST /call/<step>``, the reply validated against the step's reply model.

    The client file is read on every call; gone, it raises ``ClientFileError``
    naming it, and no local store is opened (D3). Each reply's work keys go into
    ``last`` for the after-step.
    """

    def __init__(self, last: LastReply, times: DoorTimes = DoorTimes()) -> None:  # noqa: B008  frozen
        #: What this command's last reply said about waiting work.
        self.last = last
        self._times = times

    def run[Request: StepModel, Reply: StepModel](
        self, step: Step[Request, Reply], request: Request
    ) -> Reply:
        cert_path = pinned_cert_path()
        client_file = load_client_file(client_file_path(), cert_path)
        document = request.model_dump(mode="json")
        try:
            result = call(client_file, cert_path, step.name, document, self._times)
        except HubUnreachableError:
            self.last.unreachable = True
            raise
        take_work_keys(result, self.last)
        try:
            return step.reply.model_validate(result)
        except ValidationError as error:
            fields = ", ".join(
                ".".join(str(part) for part in problem["loc"]) or "(the reply)"
                for problem in error.errors()
            )
            applied = " The hub applied the step." if step.keeps_result else ""
            raise StepReplyError(
                f"the reply to step {step.name} does not fit its model at {fields}."
                f"{applied}"
            ) from error


@contextmanager
def steps_for(
    layout: StateLayout, last: LastReply, load_config: Callable[[], UserConfig]
) -> Generator[Steps]:
    """The steps one command uses to its end: ``DoorSteps`` when a client file
    exists, otherwise ``LocalSteps`` on the local store, opened here and closed when
    the command is done. ``load_config`` is called only by a local step that needs
    the config."""
    if client_file_path().exists():
        yield DoorSteps(last)
        return
    with open_state_store(layout) as store:
        yield LocalSteps(store, StepEdges(lambda: datetime.now(UTC), load_config))


def after_operation(  # noqa: PLR0913 - what the after-step is given
    name: OperationName,
    document: object,
    steps: Steps | None,
    last: LastReply,
    deps: Callable[[], Deps],
) -> None:
    """The after-step of ``wiring.invoke`` when its door runs one. ``status`` and the
    default ``list`` view prune in their own placement, so the after-step does not prune
    after them."""
    pruned_already = name is OperationName.STATUS or (
        name is OperationName.LIST and list_view.needs_here(document)
    )
    after_call(steps, deps, last, prunes=not pruned_already)


def after_call(  # noqa: PLR0913 - the pieces of one after-step
    steps: Steps | None,
    deps: Callable[[], Deps],
    last: LastReply,
    *,
    prunes: bool,
) -> None:
    """The after-step. ``steps`` is ``None`` when none can be made (a joined machine
    until its steps are the door's): nothing happens. Never raises."""
    if last.problem is not None:
        sys.stderr.write(
            "the hub could not tell whether this machine has work waiting: "
            f"{last.problem}\n"
        )
    if steps is None or last.unreachable:
        return
    try:
        run_after_step(steps, deps, last, prunes=prunes)
    except (ConfigError, AmoebaHomeError) as error:
        # Not re-raised: the call this follows has committed, so raising would report a
        # failure for work that happened. One line and no traceback: a missing or
        # invalid config is the person's to fix, not a crash. The work is found again
        # by the next call.
        logger.error("the after-step stopped; its work is found again: %s", error)
    except AFTER_STEP_ERRORS:
        # Not re-raised, for the reason above. Nothing was started; the claims, if the
        # hub applied them, run out and the work is handed out again (D10, D11).
        logger.exception("the after-step stopped; its work is found again next call")


#: What the after-step's own calls raise when they cannot finish; the work is found
#: again by the next call, so each caller logs it and goes on.
AFTER_STEP_ERRORS: Final = (
    StoreError,
    HubUnreachableError,
    HubRefusedError,
    ClientFileError,
    HubCertificateError,
    OSError,
)


def run_after_step(
    steps: Steps, deps: Callable[[], Deps], last: LastReply, *, prunes: bool
) -> None:
    """The after-step's work: the clean-up when due, then one ``claim_work`` call and
    the start of what it returns. Raises what it cannot finish (``ConfigError``,
    ``AmoebaHomeError`` and ``AFTER_STEP_ERRORS``); ``after_call`` logs it for the CLI
    and the session's runner (``mcp.after_runner``) logs it by the run.
    """
    built = deps()
    if prunes:
        _prune(steps, built)
    if _work_waiting(steps, last):
        reply = steps.run(CLAIM_WORK, ClaimWorkRequest(logs_dir=str(built.logs_dir)))
        start_claimed(steps, built, reply.items)


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
