"""Where ``add``, ``rm`` and ``list`` get their arguments placed (slice 229, D1 to D3).

``wiring.invoke`` opens the store and loads the config and dependencies; each helper
here only places them, as ``set_up`` was placed before: ``add`` and ``rm`` run ``cf``
with ``subprocess.run`` from the caller's directory, and ``list`` takes the
dependencies the read-side operations take.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations.add import add
from amoeba.operations.add_gather import gather_add
from amoeba.operations.deps import Deps
from amoeba.operations.here import gather_caller
from amoeba.operations.list_view import ListOutcome, list_view, needs_here
from amoeba.operations.names import Door
from amoeba.operations.rm import needs_here as rm_needs_here
from amoeba.operations.rm import rm
from amoeba.operations.set_up_models import SetUpResult
from amoeba.store.store import Store


def place_add(
    store: Store, config: UserConfig, document: object, directory: Path, door: Door
) -> SetUpResult:
    # The client part first (D5): the door's refusal, then what the directory gives.
    gathered = gather_add(document, directory, subprocess.run, subprocess.run, door)
    if isinstance(gathered, SetUpResult):
        return gathered
    return add(store, config, document, here=gathered)


def place_rm(
    store: Store, config: UserConfig, document: object, directory: Path
) -> SetUpResult:
    # The client part first, only when nothing says which program or checkout is meant
    # (D5): ``rm <name>`` and ``rm --checkout`` gather nothing, so they run no ``cf``.
    here = gather_caller(directory, subprocess.run) if rm_needs_here(document) else None
    return rm(store, config, document, here=here)


def place_list(
    store: Store,
    config: UserConfig,
    document: object,
    directory: Path,
    deps: Deps,
) -> ListOutcome:
    # The client part first, only for the default view (D5): ``list members`` and the
    # other subjects read the store and need no ``cf`` call.
    here = gather_caller(directory, deps.cf_run) if needs_here(document) else None
    return list_view(store, config, document, directory=directory, here=here, deps=deps)
