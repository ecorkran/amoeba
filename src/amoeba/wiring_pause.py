"""``handle_pause`` bound to its steps: the register callable, the file clean-up and
the start of waiting work (slice 262). ``handle_pause_in`` is the command's, on the
steps ``steps_for`` picks; ``handle_pause_locally`` runs on a store the caller opened.

The file clean-up and the start of waiting work (the after-step) are bound here,
beside the steps, and never inside the pause modules.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from pathlib import Path

from amoeba.client.errors import HubRefusedError, HubUnreachableError
from amoeba.config.home import StateLayout
from amoeba.config.user_config import UserConfig
from amoeba.operations.add_register import in_process_register
from amoeba.operations.deps import Deps
from amoeba.operations.handle_pause import HandlePauseResult, handle_pause
from amoeba.operations.names import OperationName
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.models import OPEN_RUNS
from amoeba.operations.steps.models_runs import OpenRunsReply, OpenRunsRequest
from amoeba.operations.store_steps import LocalSteps, Steps
from amoeba.store.errors import StoreError
from amoeba.store.store import Store
from amoeba.store.vocabulary import Door
from amoeba.wiring_door import route
from amoeba.wiring_steps import DoorSteps, LastReply, after_call, steps_for

logger = logging.getLogger(__name__)


def handle_pause_in(
    layout: StateLayout,
    load_config: Callable[[], UserConfig],
    run_id: str,
    *,
    directory: Path,
    deps: Deps,
) -> HandlePauseResult:
    """Handle ``run_id``'s pause on the steps this command uses to its end: the door's
    when this machine is joined, the local store's otherwise (262 D3).

    Raises:
        As ``handle_pause`` does, and ``ClientFileError`` when the client file goes.
    """
    last = LastReply()
    with steps_for(layout, last, load_config) as steps:
        if isinstance(steps, DoorSteps):
            register = _door_register(steps, deps)
        elif isinstance(steps, LocalSteps):
            register = in_process_register(steps.store, load_config, deps)
        else:
            raise AssertionError(f"steps_for gave {type(steps).__name__}")
        return handle_pause_with(steps, last, run_id, directory, deps, register)


def handle_pause_locally(
    store: Store, config: UserConfig, run_id: str, *, directory: Path, deps: Deps
) -> HandlePauseResult:
    """Handle ``run_id``'s pause on a local store the caller opened.

    Raises:
        As ``handle_pause`` does.
    """
    steps = LocalSteps(store, StepEdges(deps.clock, lambda: config))
    register = in_process_register(store, lambda: config, deps)
    return handle_pause_with(steps, LastReply(), run_id, directory, deps, register)


def handle_pause_with(  # noqa: PLR0913 - what one handle_pause is bound to
    steps: Steps,
    last: LastReply,
    run_id: str,
    directory: Path,
    deps: Deps,
    register: Callable[[Path], SetUpResult],
) -> HandlePauseResult:
    """``handle_pause`` on ``steps``, with the clean-up note and the after-step bound
    to them."""
    return handle_pause(
        steps,
        run_id,
        directory=directory,
        deps=deps,
        register=register,
        prune_note=partial(_prune_note, steps, deps),
        after=partial(after_call, steps, lambda: deps, last, prunes=False),
    )


def _door_register(steps: DoorSteps, deps: Deps) -> Callable[[Path], SetUpResult]:
    """``register`` on a joined machine: ``add`` placed through the door, as a bare
    ``amoeba add`` in the checkout would be."""

    def register(directory: Path) -> SetUpResult:
        result = route(OperationName.ADD, {}, directory, Door.CLI, lambda: deps, steps)
        if not isinstance(result, SetUpResult):
            raise AssertionError("add through the door returns a set-up result")
        return result

    return register


def _prune_note(steps: Steps, deps: Deps) -> str | None:
    """What pruning could not do, as a note. A failure here is a note, not an error:
    the result is already decided, and a resume may already have been delivered, so
    raising would report a failure for work that happened."""

    def open_runs() -> OpenRunsReply:
        return steps.run(OPEN_RUNS, OpenRunsRequest())

    try:
        pruned = deps.prune(open_runs, now=deps.clock())
    except (StoreError, HubUnreachableError, HubRefusedError) as error:
        logger.exception("prune failed after handling the pause")
        return f"prune: {error}"
    return pruned.note()
