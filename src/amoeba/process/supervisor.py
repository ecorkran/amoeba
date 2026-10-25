"""What the supervisor directory contains, and the observers to reconcile it.

Separate from ``host.py`` so the loop module stays near its line budget. Project
discovery itself lives in ``amoeba.store.discovery``.

Nothing here opens a store read-write; ``project_stores.py`` remains the only
module permitted to do that. Recovery receives stores already open.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from amoeba.process.errors import StartupFailedError
from amoeba.process.observers.cf_readback import CFReadbackObserver
from amoeba.process.observers.sq_run_id import (
    SquadronRunIdObserver,
    SquadronRunObserver,
)
from amoeba.process.observers.sq_runs import SquadronRunsObserver
from amoeba.process.recovery import ObserverRegistry, reconcile
from amoeba.process.settings import ProcessSettings
from amoeba.store import Store
from amoeba.store.journal_models import CommandKind
from amoeba.store.paths import project_store_path

logger = logging.getLogger(__name__)


def store_path_for(store_dir: Path, project_id: str) -> Path:
    """The store file for a project inside a given supervisor directory."""
    return project_store_path(store_dir, project_id)


def build_observer_registry(
    settings: ProcessSettings,
    claimed_run_ids: Mapping[str, str] | None = None,
    claimed_run_nodes: Mapping[str, str] | None = None,
) -> ObserverRegistry:
    """Assemble the observers for **one** recovery pass.

    An ``sq_run`` entry that carries a run id is answered by ``sq runs wait``
    and reads no run-state file. The legacy attribute matcher, for entries
    journaled before slice 120, scans the runs directory lazily: at most once
    per pass, and only if a legacy entry exists. The ``cf --version`` label is
    captured at most once. The load tier asserts the scan and poll counts.

    Args:
        settings: Supplies the launch grace, the ``sq`` timeout, the legacy
            runs directory and clock tolerance, and the cf timeout.
        claimed_run_ids: Run ids already recorded in another entry's result,
            which are therefore not candidates for any further entry.
        claimed_run_nodes: The same run ids mapped to the node that owns the
            recording entry, for a continuation's claimed-id guard.
    """
    return {
        CommandKind.SQ_RUN: SquadronRunObserver(
            by_id=SquadronRunIdObserver(
                launch_grace_seconds=settings.launch_grace_seconds,
                poll_timeout_seconds=settings.sq_timeout_seconds,
                claimed_run_ids=claimed_run_ids,
                claimed_run_nodes=claimed_run_nodes,
                now=lambda: datetime.now(UTC),
                sleep=time.sleep,
            ),
            legacy=SquadronRunsObserver(
                settings.sq_runs_dir,
                clock_tolerance_seconds=settings.clock_tolerance_seconds,
                claimed_run_ids=claimed_run_ids,
                scan=None,
            ),
        ),
        CommandKind.CF_WRITE: CFReadbackObserver(
            timeout_seconds=settings.cf_timeout_seconds
        ),
    }


def recover_every_project(
    projects: Iterable[tuple[str, Store]], settings: ProcessSettings
) -> None:
    """Reconcile every project, each against a freshly assembled registry.

    The host calls this before any tenant ticks: recovery gates the loop.

    Raises:
        StartupFailedError: If recovery fails for any project. The process
            does not enter the loop against unreconciled state.
    """
    for project_id, store in projects:
        try:
            registry = build_observer_registry(
                settings,
                store.recorded_result_run_ids(project_id),
                store.recorded_result_run_nodes(project_id),
            )
            summary = reconcile(store, project_id, registry)
        except Exception as error:
            logger.exception("recovery failed for project %s", project_id)
            raise StartupFailedError(
                f"recovery failed for project {project_id!r}: {error}"
            ) from error

        logger.info("recovery %s: %s", project_id, summary.describe())
