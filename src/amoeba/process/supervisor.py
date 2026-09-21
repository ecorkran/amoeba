"""What the supervisor directory contains, and the observers to reconcile it.

Separate from ``host.py`` so the loop module stays near its line budget, and so
the CLI's inspection path can discover projects without importing the host.

Neither function opens a store read-write; ``host.py`` remains the only module
permitted to do that.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from amoeba.process.observers.cf_readback import CFReadbackObserver
from amoeba.process.observers.sq_runs import SquadronRunsObserver, scan_runs_directory
from amoeba.process.recovery import ObserverRegistry
from amoeba.process.settings import ProcessSettings
from amoeba.store.journal_models import CommandKind
from amoeba.store.paths import STORE_FILE_SUFFIX


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
