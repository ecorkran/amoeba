"""Where ``send``, ``inbox``, ``reply`` and ``cancel`` get their arguments placed
(slice 240, D3, Timeouts).

``wiring.invoke`` opens the store and builds the dependencies; this only picks the
operation and hands it the store, the config, the document, the caller's directory
and the dependencies. It also holds what bounds each call's worst-case time, which
the tool descriptions state and ``tests/test_message_timing.py`` checks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, assert_never

from amoeba.config.user_config import UserConfig
from amoeba.operations.cancel import cancel
from amoeba.operations.deps import Deps
from amoeba.operations.inbox import inbox
from amoeba.operations.message_results import (
    CancelResult,
    InboxResult,
    ReplyResult,
    SendResult,
)
from amoeba.operations.names import OperationName
from amoeba.operations.reply import reply
from amoeba.operations.send import send
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.upstream.context_forge.project_of import CF_GET_TIMEOUT_SECONDS

type MessageOperation = Literal[
    OperationName.SEND,
    OperationName.INBOX,
    OperationName.REPLY,
    OperationName.CANCEL,
]
type MessageResult = SendResult | InboxResult | ReplyResult | CancelResult

#: The most ``cf`` lookups each operation makes: the caller's directory, an explicit
#: ``member`` (counted whether or not one is given), and for ``send`` the recipient.
MESSAGE_LOOKUPS: Final = {
    OperationName.SEND: 3,
    OperationName.INBOX: 2,
    OperationName.REPLY: 2,
    OperationName.CANCEL: 2,
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


def place_message(
    name: MessageOperation,
    store: Store,
    config: UserConfig,
    document: object,
    directory: Path,
    deps: Deps,
) -> MessageResult:
    match name:
        case OperationName.SEND:
            return send(store, config, document, directory=directory, deps=deps)
        case OperationName.INBOX:
            return inbox(store, document, directory=directory, deps=deps)
        case OperationName.REPLY:
            return reply(store, config, document, directory=directory, deps=deps)
        case OperationName.CANCEL:
            return cancel(store, config, document, directory=directory, deps=deps)
        case _:
            assert_never(name)
