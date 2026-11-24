"""``prune`` on a local store, the way the local way calls it (slice 262, D12)."""

from __future__ import annotations

from datetime import datetime

from user_configs import user_config

from amoeba.config.home import StateLayout
from amoeba.operations.prune import prune
from amoeba.operations.prune_models import PruneReport
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.models import OPEN_RUNS
from amoeba.operations.steps.models_runs import OpenRunsReply, OpenRunsRequest
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.store import Store


def open_runs_of(store: Store, now: datetime) -> OpenRunsReply:
    """What ``open_runs`` says on this store: the machine's open runs and the
    config's ``prune_after_days``."""
    steps = LocalSteps(store, StepEdges(lambda: now, user_config))
    return steps.run(OPEN_RUNS, OpenRunsRequest())


def prune_store(store: Store, layout: StateLayout, now: datetime) -> PruneReport:
    """``prune`` with ``open_runs`` read from ``store``, once, when a walk is due."""
    return prune(lambda: open_runs_of(store, now), layout, now)
