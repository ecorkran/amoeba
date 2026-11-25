"""Log records for a person at a terminal: the message lines, without tracebacks.

The library logs a failure with its traceback (``logger.exception``) before raising
it, and the command then reports the raised error once, as its ``error:`` line. With
no handler installed, Python's last-resort handler prints the record and its
traceback to stderr. That is right for a captured stderr (a hook's, a wake's or a
resume's ``.stderr.log``), where the traceback is the diagnosis, and wrong for a
person, who reads a dozen lines to find one fact. So a terminal gets the message
lines only, and a stderr that is not a terminal is left exactly as it was.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from types import TracebackType
from typing import Final, TextIO

TERMINAL_LOG_LEVEL: Final = logging.WARNING
TERMINAL_LOG_FORMAT: Final = "%(message)s"

type _ExcInfo = (
    tuple[type[BaseException], BaseException, TracebackType | None]
    | tuple[None, None, None]
)


class MessageOnlyFormatter(logging.Formatter):
    """A record's message; the traceback of a logged exception is left out."""

    def formatException(self, ei: _ExcInfo) -> str:
        return ""


@contextmanager
def terminal_log(stream: TextIO) -> Generator[None]:
    """While open, a terminal ``stream`` shows warnings and errors as message lines.

    A ``stream`` that is not a terminal gets no handler: nothing changes for it.
    """
    if not stream.isatty():
        yield
        return
    handler = logging.StreamHandler(stream)
    handler.setLevel(TERMINAL_LOG_LEVEL)
    handler.setFormatter(MessageOnlyFormatter(TERMINAL_LOG_FORMAT))
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield
    finally:
        root.removeHandler(handler)
