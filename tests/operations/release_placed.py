"""``changes`` and ``report_release`` as the placement calls them: the client part
first (one ``cf get`` of the directory), then the operation on the gathered ``here``
(slice 261, D5). Tests import these in place of the operations, keeping the shape
``directory=...``."""

from __future__ import annotations

from pathlib import Path

from amoeba.operations import changes as changes_module
from amoeba.operations import report_release as report_release_module
from amoeba.operations.changes_models import ChangesResult
from amoeba.operations.deps import Deps
from amoeba.operations.here import gather_caller
from amoeba.operations.report_release_models import ReportReleaseResult
from amoeba.store.store import Store


def changes(
    store: Store, document: object, *, directory: Path, deps: Deps
) -> ChangesResult:
    here = gather_caller(directory, deps.cf_run)
    return changes_module.changes(store, document, here=here)


def report_release(
    store: Store, document: object, *, directory: Path, deps: Deps
) -> ReportReleaseResult:
    here = gather_caller(directory, deps.cf_run)
    return report_release_module.report_release(
        store, document, here=here, clock=deps.clock
    )
