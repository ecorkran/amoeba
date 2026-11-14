"""Where ``report_release`` and ``changes`` get their arguments placed (slice 227, D5).

``wiring.invoke`` opens the store and builds the dependencies; this only picks the
operation, which both take the caller's directory and the dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from amoeba.operations.changes import changes
from amoeba.operations.changes_models import ChangesResult
from amoeba.operations.deps import Deps
from amoeba.operations.names import OperationName
from amoeba.operations.report_release import report_release
from amoeba.operations.report_release_models import ReportReleaseResult
from amoeba.store.store import Store


def place_release(
    name: Literal[OperationName.REPORT_RELEASE, OperationName.CHANGES],
    store: Store,
    document: object,
    directory: Path,
    deps: Deps,
) -> ReportReleaseResult | ChangesResult:
    if name is OperationName.REPORT_RELEASE:
        return report_release(store, document, directory=directory, deps=deps)
    return changes(store, document, directory=directory, deps=deps)
