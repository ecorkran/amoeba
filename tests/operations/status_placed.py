"""``status`` and ``list_view`` as the placement calls them: the client part first
(one ``cf get`` of the directory), then the operation on the gathered ``here``
(slice 261, D5). Tests import these in place of the operations, keeping the shape
``directory=...``.

``list_view`` gathers only for the default view, as ``wiring_registry.place_list`` does.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations import list_view as list_view_module
from amoeba.operations import status as status_module
from amoeba.operations.deps import Deps
from amoeba.operations.here import gather_caller
from amoeba.operations.list_view import ListOutcome, needs_here
from amoeba.operations.status_models import StatusResult
from amoeba.store.store import Store


def status(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    directory: Path,
    deps: Deps,
) -> StatusResult:
    here = gather_caller(directory, deps.cf_run)
    return status_module.status(
        store, config, document, directory=directory, here=here, deps=deps
    )


def list_view(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    directory: Path,
    deps: Deps,
) -> ListOutcome:
    here = gather_caller(directory, deps.cf_run) if needs_here(document) else None
    return list_view_module.list_view(
        store, config, document, directory=directory, here=here, deps=deps
    )
