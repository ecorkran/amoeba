"""Where ``report_release`` and ``changes`` get their arguments placed (slice 227, D5).

``wiring.invoke`` opens the store and builds the dependencies; this only picks the
operation, which both take the gathered caller and the dependencies.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from amoeba.config.user_config import UserConfig
from amoeba.operations.changes import changes
from amoeba.operations.changes_models import ChangesResult
from amoeba.operations.deps import Deps
from amoeba.operations.here import gather_caller
from amoeba.operations.message_sweep import sweep_messages
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
    load_config: Callable[[], UserConfig],
) -> ReportReleaseResult | ChangesResult:
    # The client part first: a ``cf`` failure raises here, before any store work.
    here = gather_caller(directory, deps.cf_run)
    if name is OperationName.REPORT_RELEASE:
        # Every write that adds a note also sweeps (243 D6). Before the report's own
        # transaction, in its own ones. A held store comes back as the sweep's problem
        # text; the report still runs and its result carries the text. Any other
        # StoreError propagates (exit 3).
        sweep_problem = sweep_messages(store, load_config(), deps.clock())
        result = report_release(store, document, here=here, deps=deps)
        return result.model_copy(update={"sweep_problem": sweep_problem})
    return changes(store, document, here=here, deps=deps)
