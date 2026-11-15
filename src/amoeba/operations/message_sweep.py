"""The message sweep for callers that only read (slice 240, D6).

``status``, ``list`` and ``handle_pause`` call this. It reads first and opens a write
transaction only when something is due, so a poll of a quiet store never write-locks
it. ``send``, ``reply`` and ``cancel`` call the store's ``sweep`` inside their own
write transaction instead.
"""

from __future__ import annotations

import logging
from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.store.errors import StoreBusyError
from amoeba.store.message_sweep import sweep, sweep_due
from amoeba.store.store import Store

logger = logging.getLogger(__name__)


def sweep_messages(store: Store, config: UserConfig, now: datetime) -> str | None:
    """Sweep what is due; the text of a problem, or ``None`` when all went well.

    A store that stays locked for the whole busy timeout is not raised: the caller's
    read still returns, because every read applies ``effective_state`` and shows
    nothing wrong, and the next call sweeps. Any other ``StoreError`` propagates.

    Raises:
        StoreError: The store cannot be used for a reason other than a busy lock.
    """
    try:
        with store.read() as transaction:
            due = sweep_due(transaction, now, config.prune_after_days)
        if not due:
            return None
        with store.write() as transaction:
            sweep(transaction, now, config.prune_after_days)
    except StoreBusyError as error:
        # The store is busy, not broken: the caller still returns its read, which
        # applies effective_state, and a later call sweeps what was due.
        logger.exception("the message sweep could not take the store lock")
        return f"message sweep did not run: {error}"
    return None
