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
from amoeba.store.errors import StoreError
from amoeba.upstream.squadron.errors import SquadronError


class ContextForgeError(Exception):
    """``cf`` is not working: not a member, and not a non-member either."""


class DeadlineError(Exception):
    """The config lets an ``answer`` run past the MCP call deadline."""


#: The two refusals a hub part makes itself (slice 261, D12). Plain strings, so
#: ``operations`` imports nothing from ``wire``; a test pins each to a
#: ``RefusalCode`` value.
MALFORMED_CALL: Final = "malformed_call"
NOT_SERVED: Final = "not_served"


class CallRefused(Exception):  # noqa: N818 - named for the refusal, as designed
    """A hub part refuses the call: a missing or bad gathered value, or an
    operation the door does not serve yet.

    Not in ``OPERATION_ERRORS``: only ``hub.calls.handle_call`` catches it, and with
    no client file it is a bug that nothing catches (D12).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


#: Config, home, Context Forge, Squadron and store failures.
OPERATION_ERRORS: Final = (
    AmoebaHomeError,
    ConfigError,
    ContextForgeError,
    DeadlineError,
    SquadronError,
    StoreError,
)
