"""What bounds the worst-case time of ``send``, ``inbox``, ``reply`` and ``cancel``
(slice 240, Timeouts), which the tool descriptions state and
``tests/test_message_timing.py`` checks. The placement itself is
``wiring_gather.place_served``."""

from __future__ import annotations

from typing import Final, Literal

from amoeba.operations.message_results import (
    CancelResult,
    InboxResult,
    ReplyResult,
    SendResult,
)
from amoeba.operations.names import OperationName
from amoeba.store.store import BUSY_TIMEOUT_SECONDS
from amoeba.upstream.context_forge.project_of import CF_GET_TIMEOUT_SECONDS

type MessageOperation = Literal[
    OperationName.SEND,
    OperationName.INBOX,
    OperationName.REPLY,
    OperationName.CANCEL,
]
type MessageResult = SendResult | InboxResult | ReplyResult | CancelResult

#: The ``cf`` lookups each operation makes: the one ``cf get`` of the caller's
#: directory, in the client part (``operations.here``). A named recipient or member is
#: a store read (261 D6, D10).
MESSAGE_LOOKUPS: Final = {
    OperationName.SEND: 1,
    OperationName.INBOX: 1,
    OperationName.REPLY: 1,
    OperationName.CANCEL: 1,
}
#: Store waits one call can make, each at most one busy timeout: the legacy-move lock,
#: the store open and the operation's own transaction.
MESSAGE_STORE_WAITS: Final = 3


def worst_case_seconds(name: MessageOperation) -> float:
    """The longest ``name`` can take: its ``cf`` lookups at their timeout, plus the
    store waits. 240 starts no runs, so there is no run-start term."""
    return (
        MESSAGE_LOOKUPS[name] * CF_GET_TIMEOUT_SECONDS
        + MESSAGE_STORE_WAITS * BUSY_TIMEOUT_SECONDS
    )
