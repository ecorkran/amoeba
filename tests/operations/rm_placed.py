"""``rm`` as the placement calls it: the client part first, only when nothing says
which program or checkout is meant (slice 261, D5), then the operation. Tests import
this in place of ``operations.rm.rm``, keeping the shape ``directory=...``,
``run=...``."""

from __future__ import annotations

from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations import rm as rm_module
from amoeba.operations.here import gather_caller
from amoeba.operations.set_up_models import SetUpResult
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfRun


def rm(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    directory: Path,
    run: CfRun,
) -> SetUpResult:
    here = gather_caller(directory, run) if rm_module.needs_here(document) else None
    return rm_module.rm(store, config, document, here=here)
