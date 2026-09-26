"""What the supervisor directory contains, and the observers to reconcile it.

Separate from ``host.py`` so the loop module stays near its line budget, and so
the CLI's inspection path can discover projects without importing the host.

Nothing here opens a store read-write; ``project_stores.py`` remains the only
module permitted to do that. Recovery receives stores already open.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path

from amoeba.process.errors import StartupFailedError
from amoeba.process.observers.cf_readback import CFReadbackObserver
from amoeba.process.observers.sq_runs import SquadronRunsObserver, scan_runs_directory
from amoeba.process.recovery import ObserverRegistry, reconcile
from amoeba.process.settings import ProcessSettings
from amoeba.store import Store
from amoeba.store.journal_models import CommandKind
from amoeba.store.paths import STORE_FILE_SUFFIX

logger = logging.getLogger(__name__)


def discover_project_ids(store_dir: Path) -> list[str]:
    """Project ids having a store in the supervisor directory.

    An absent directory yields no projects rather than an error: a supervisor
    that has never run is a valid, empty state — which is what
    ``amoeba inspect projects`` reports against a fresh directory.
    """
    if not store_dir.is_dir():
        return []
    return sorted(
        path.name[: -len(STORE_FILE_SUFFIX)]
        for path in store_dir.glob(f"*{STORE_FILE_SUFFIX}")
        if path.is_file()
    )


def store_path_for(store_dir: Path, project_id: str) -> Path:
    """The store file for a project inside a given supervisor directory."""
    return store_dir / f"{project_id}{STORE_FILE_SUFFIX}"


def build_observer_registry(
    settings: ProcessSettings, claimed_run_ids: Mapping[str, str] | None = None
) -> ObserverRegistry:
    """Assemble the observers for **one** recovery pass.

    The runs directory is scanned once here rather than once per entry, and the
    ``cf --version`` label is captured at most once, so reconciling many
    entries costs one directory read and one version call. The load tier
    asserts the scan count exactly.

    Args:
        settings: Supplies the runs directory, clock tolerance, and cf timeout.
        claimed_run_ids: Run ids already recorded in another entry's result,
            which are therefore not candidates for any further entry.
    """
    return {
        CommandKind.SQ_RUN: SquadronRunsObserver(
            settings.sq_runs_dir,
            clock_tolerance_seconds=settings.clock_tolerance_seconds,
            claimed_run_ids=claimed_run_ids,
            scan=scan_runs_directory(settings.sq_runs_dir),
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
                settings, store.recorded_result_run_ids(project_id)
            )
            summary = reconcile(store, project_id, registry)
        except Exception as error:
            logger.exception("recovery failed for project %s", project_id)
            raise StartupFailedError(
                f"recovery failed for project {project_id!r}: {error}"
            ) from error

        logger.info("recovery %s: %s", project_id, summary.describe())
