"""Where ``standing`` and ``withdraw`` get their arguments placed (slice 230, D2, D3).

``wiring.invoke`` opens the store and builds the dependencies; this only picks the
operation and hands it the store, the document and the clock, and ``standing`` also
the passage cap and ``cf``. Config is loaded only for ``standing``, so ``withdraw``,
like ``dismiss`` and ``retract``, runs with a missing or broken config file. Neither
takes the caller's directory: ``--member`` is resolved through ``cf`` with no working
directory.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, assert_never

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.names import OperationName
from amoeba.operations.standing import standing
from amoeba.operations.standing_models import StandingResult, WithdrawResult
from amoeba.operations.withdraw import withdraw
from amoeba.store.store import Store

type StandingOperation = Literal[OperationName.STANDING, OperationName.WITHDRAW]


def place_standing(
    name: StandingOperation,
    store: Store,
    load_config: Callable[[], UserConfig],
    document: object,
    deps: Deps,
) -> StandingResult | WithdrawResult:
    match name:
        case OperationName.STANDING:
            return standing(
                store,
                document,
                max_chars=load_config().passages_max_chars,
                run=deps.cf_run,
                now=deps.clock(),
            )
        case OperationName.WITHDRAW:
            return withdraw(store, document, now=deps.clock())
        case _:
            assert_never(name)
