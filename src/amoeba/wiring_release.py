"""Start ``handle-pause`` for held questions after the operations that could have
ended their request (slice 242, D7).

``wiring.invoke`` calls :func:`start_after` once, after any operation's transaction
has closed, for both doors. Only the names in ``START_AFTER_OPERATIONS`` start
anything; ``inbox`` stays a read. The config and deps are built only for those names,
each of which has already loaded the config for its own work.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Final

from amoeba.config.home import AmoebaHomeError
from amoeba.config.user_config import ConfigError, UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.names import OperationName
from amoeba.operations.request_release import start_ended_held
from amoeba.store.store import Store

logger = logging.getLogger(__name__)

#: The operations after which held questions whose request ended are started: the
#: three that end requests, the two whose cascade or expiry can, and the two reads a
#: person runs to look.
START_AFTER_OPERATIONS: Final = frozenset(
    {
        OperationName.SEND,
        OperationName.REPLY,
        OperationName.CANCEL,
        OperationName.ADD,
        OperationName.RM,
        OperationName.STATUS,
        OperationName.LIST,
    }
)


def start_after(
    name: OperationName,
    store: Store,
    config: Callable[[], UserConfig],
    deps: Callable[[], Deps],
) -> None:
    """Run ``start_ended_held`` after ``name`` when it is one of
    ``START_AFTER_OPERATIONS``. Never changes the operation's result and never
    raises: ``start_ended_held`` logs its own failures, and so does this for the
    config and deps it builds."""
    if name not in START_AFTER_OPERATIONS:
        return
    try:
        loaded, built = config(), deps()
    except (ConfigError, AmoebaHomeError):
        # Not re-raised: the operation's own work has committed, so raising would
        # report a failure for work that happened, or replace the operation's own
        # error. The held rows are found again by the next call.
        logger.exception("could not build the config or deps to start held questions")
        return
    start_ended_held(store, loaded, built)
