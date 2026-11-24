"""``handle_pause`` on the local way: the steps, the register callable, the file
clean-up and the start of waiting work, bound to one open store (slice 262).

Until the after-step replaces ``start_ended_held`` and the prune moves onto steps
(262 tasks 5.5 and 6.5), the clean-up and the start still need the store and config:
they are bound here, beside the steps, and never inside the pause modules.
"""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations.add_register import in_process_register
from amoeba.operations.deps import Deps
from amoeba.operations.handle_pause import HandlePauseResult, handle_pause
from amoeba.operations.request_release import start_ended_held
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.errors import StoreError
from amoeba.store.store import Store

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
        prune_note=partial(_prune_note, store, config, deps),
        after=partial(start_ended_held, store, config, deps),
    )


def _prune_note(store: Store, config: UserConfig, deps: Deps) -> str | None:
    """What pruning could not do, as a note. A store failure here is a note, not an
    error: the result is already decided, and a resume may already have been
    delivered, so raising would report a failure for work that happened."""
    try:
        pruned = deps.prune(store, now=deps.clock(), after_days=config.prune_after_days)
    except StoreError as error:
        logger.exception("prune failed after handling the pause")
        return f"prune: {error}"
    return pruned.note()
