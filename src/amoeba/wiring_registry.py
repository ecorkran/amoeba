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
from amoeba.operations.deps import Deps
from amoeba.operations.list_view import ListOutcome, list_view
from amoeba.operations.rm import rm
from amoeba.operations.set_up_models import SetUpResult
from amoeba.store.store import Store


def place_add(
    store: Store, config: UserConfig, document: object, directory: Path
) -> SetUpResult:
    return add(store, config, document, directory=directory, run=subprocess.run)


def place_rm(
    store: Store, config: UserConfig, document: object, directory: Path
) -> SetUpResult:
    return rm(store, config, document, directory=directory, run=subprocess.run)


def place_list(
    store: Store,
    config: UserConfig,
    document: object,
    directory: Path,
    deps: Deps,
) -> ListOutcome:
    return list_view(store, config, document, directory=directory, deps=deps)
