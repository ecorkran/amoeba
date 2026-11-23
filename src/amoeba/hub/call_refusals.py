"""Refusing a call, and logging it (slice 260, D6, D8, D16).

A refused reply names a code from ``RefusalCode`` and carries that code's HTTP status.
An exception that reaches the hub's boundary is mapped here: one of the operations'
own failures is ``hub_error`` with ``<ErrorName>: <text>``, anything else is
``hub_fault``, logged with its traceback.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from amoeba.hub.hub_log import refusal_line
from amoeba.operations.errors import OPERATION_ERRORS
from amoeba.wire.protocol import REFUSAL_STATUS, RefusalCode, refused_reply

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CallReply:
    """What ``handle_call`` returns: an HTTP status and a body."""

    status: int
    body: bytes


def refused(code: RefusalCode, message: str) -> CallReply:
    """A refused reply for ``code`` with its status."""
    return CallReply(REFUSAL_STATUS[code], refused_reply(code, message))


@dataclass(frozen=True)
class Refuser:
    """Builds a refused reply and writes its log line, for one call."""

    clock: Callable[[], datetime]
    peer: str

    def refuse(
        self, code: RefusalCode, message: str, machine: str | None = None
    ) -> CallReply:
        """Log the refusal (never the token, body or document) and return it."""
        logger.warning(refusal_line(self.clock(), self.peer, code.value, machine))
        return refused(code, message)

    def for_exception(self, error: Exception, machine: str | None) -> CallReply:
        """The refusal an exception raised while serving a call becomes.

        One of the operations' own errors is ``hub_error``, ``<ErrorName>: <text>``.
        Anything else is a bug or a trigger's abort: ``hub_fault`` naming the type,
        with the traceback in the hub log.
        """
        if isinstance(error, OPERATION_ERRORS):
            return self.refuse(
                RefusalCode.HUB_ERROR, f"{type(error).__name__}: {error}", machine
            )
        logger.error("hub fault serving a call from %s", self.peer, exc_info=error)
        return self.refuse(
            RefusalCode.HUB_FAULT,
            f"{type(error).__name__}: the traceback is in the hub log",
            machine,
        )
