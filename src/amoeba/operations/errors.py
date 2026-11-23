"""The failures an operation may raise that a door reports instead of crashing on
(slice 260, D8).

``wiring.OPERATIONAL_ERRORS`` is these five plus the errors of the door's own steps
(join, the client file, the call). The hub may not import ``wiring``, so the five
live here, defined once, and the hub refuses a call as ``hub_error`` when its
operation raises one of them.
"""

from __future__ import annotations

from typing import Final

from amoeba.config.home import AmoebaHomeError
from amoeba.config.user_config import ConfigError
from amoeba.operations.members import ContextForgeError
from amoeba.store.errors import StoreError
from amoeba.upstream.squadron.errors import SquadronError

#: Config, home, Context Forge, Squadron and store failures.
OPERATION_ERRORS: Final = (
    AmoebaHomeError,
    ConfigError,
    ContextForgeError,
    SquadronError,
    StoreError,
)
