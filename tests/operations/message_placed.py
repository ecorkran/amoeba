"""``send``, ``inbox``, ``reply`` and ``cancel`` as the placement calls them: the
client part first (one ``cf get`` of the directory), then the operation on the
gathered ``here`` (slice 261, D5).

Tests that exercise the operations from a directory import these in place of the
operations themselves, so their calls keep the shape ``directory=...``.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations import cancel as cancel_module
from amoeba.operations import inbox as inbox_module
from amoeba.operations import reply as reply_module
from amoeba.operations import send as send_module
from amoeba.operations.deps import Deps
from amoeba.operations.here import gather_caller
from amoeba.operations.message_results import (
    CancelResult,
    InboxResult,
    ReplyResult,
    SendResult,
)
from amoeba.store.store import Store


def send(
    store: Store, config: UserConfig, document: object, *, directory: Path, deps: Deps
) -> SendResult:
    here = gather_caller(directory, deps.cf_run)
    return send_module.send(store, config, document, here=here, deps=deps)


def inbox(
    store: Store, document: object, *, directory: Path, deps: Deps
) -> InboxResult:
    here = gather_caller(directory, deps.cf_run)
    return inbox_module.inbox(store, document, here=here, deps=deps)


def reply(
    store: Store, config: UserConfig, document: object, *, directory: Path, deps: Deps
) -> ReplyResult:
    here = gather_caller(directory, deps.cf_run)
    return reply_module.reply(store, config, document, here=here, deps=deps)


def cancel(
    store: Store, config: UserConfig, document: object, *, directory: Path, deps: Deps
) -> CancelResult:
    here = gather_caller(directory, deps.cf_run)
    return cancel_module.cancel(store, config, document, here=here, deps=deps)
