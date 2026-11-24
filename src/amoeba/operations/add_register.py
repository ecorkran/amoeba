"""Register the project a pause came from with ``add``'s defaults (slice 262, D5).

``handle_pause`` is handed this as its ``register`` callable: it gathers the checkout
as a bare ``amoeba add`` there would and runs ``add`` with an empty document. Built in
``wiring`` from the placement ``amoeba add`` itself uses; the pause modules import
neither ``add`` nor the store.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations.add import add
from amoeba.operations.add_gather import gather_add
from amoeba.operations.deps import Deps
from amoeba.operations.set_up_models import SetUpResult
from amoeba.store.store import Store
from amoeba.store.vocabulary import Door


def in_process_register(
    store: Store, load_config: Callable[[], UserConfig], deps: Deps
) -> Callable[[Path], SetUpResult]:
    """``register`` for the local way: the client part, then the hub part in process.
    The config is loaded only when a project is registered."""

    def register(directory: Path) -> SetUpResult:
        gathered = gather_add({}, directory, deps.cf_run, deps.git_run, Door.CLI)
        if isinstance(gathered, SetUpResult):
            raise ValueError("an empty add document is never refused by the CLI door")
        return add(store, load_config(), {}, here=gathered)

    return register
