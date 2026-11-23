"""``add`` as the placement calls it: the client part first, then the operation on what
it gathered (slice 261, D5). Tests import this in place of ``operations.add.add``,
keeping the shape ``directory=...``, ``run=...``, ``door=...``.

``git`` is a stub for a repo with no ``origin`` remote unless a test gives one."""

from __future__ import annotations

from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations import add as add_module
from amoeba.operations.add_gather import gather_add
from amoeba.operations.set_up_models import SetUpResult
from amoeba.store.store import Store
from amoeba.store.vocabulary import Door
from amoeba.upstream.context_forge.cli_call import CfRun
from operations.set_up_support import no_origin_git


def add(  # noqa: PLR0913 - the shape the operation had before the split
    store: Store,
    config: UserConfig,
    document: object,
    *,
    directory: Path,
    run: CfRun,
    door: Door,
    git: CfRun = no_origin_git,
) -> SetUpResult:
    gathered = gather_add(document, directory, run, git, door)
    if isinstance(gathered, SetUpResult):
        return gathered
    return add_module.add(store, config, document, here=gathered)
