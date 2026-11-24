"""``handle_pause`` on the local way: the steps, the register callable, the file
clean-up and the start of waiting work, bound to one open store (slice 262).

The file clean-up and the start of waiting work (the after-step) are bound here,
beside the steps, and never inside the pause modules.
"""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path

from amoeba.client.errors import HubRefusedError, HubUnreachableError
from amoeba.config.user_config import UserConfig
from amoeba.operations.add_register import in_process_register
from amoeba.operations.deps import Deps
from amoeba.operations.handle_pause import HandlePauseResult, handle_pause
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.models import OPEN_RUNS
from amoeba.operations.steps.models_runs import OpenRunsReply, OpenRunsRequest
from amoeba.operations.store_steps import LocalSteps, Steps
from amoeba.store.errors import StoreError
from amoeba.store.store import Store
from amoeba.wiring_steps import LastReply, after_call

logger = logging.getLogger(__name__)


def handle_pause_locally(
    store: Store, config: UserConfig, run_id: str, *, directory: Path, deps: Deps
) -> HandlePauseResult:
    """Handle ``run_id``'s pause on the local store: every step in process.

    Raises:
        As ``handle_pause`` does.
    """
    steps = LocalSteps(store, StepEdges(deps.clock, lambda: config))
    return handle_pause(
        steps,
        run_id,
        directory=directory,
        deps=deps,
        register=in_process_register(store, config, deps),
        prune_note=partial(_prune_note, steps, deps),
        after=partial(after_call, steps, lambda: deps, LastReply(), prunes=False),
    )


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
