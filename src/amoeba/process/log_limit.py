"""A byte budget for the process's log, so no fault can fill a disk with it.

A resident process logs a few lines a day when healthy. When something loops, the
log is the first thing to grow without bound (one such loop wrote over 300 GB a
day). :class:`BoundedStreamHandler` stops writing once :data:`LOG_BYTES_LIMIT`
bytes have gone out in this process's lifetime, adds one notice line saying so,
and drops the rest.
Restarting the process restores logging.
"""

from __future__ import annotations

import logging
import sys
from typing import Final, TextIO

#: Bytes one process may log before the handler goes quiet. Defined once; a
#: healthy process never comes near it.
LOG_BYTES_LIMIT: Final = 256 * 1024 * 1024

LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_NOTICE: Final = (
    "log output limit of {limit} bytes reached; further log records are dropped "
    "until this process restarts"
)


class BoundedStreamHandler(logging.StreamHandler[TextIO]):
    """A stream handler that writes at most ``limit`` bytes, then drops records."""

    def __init__(self, stream: TextIO, limit: int = LOG_BYTES_LIMIT) -> None:
        super().__init__(stream)
        self._limit = limit
        self._written = 0

    def emit(self, record: logging.LogRecord) -> None:
        if self._written >= self._limit:
            return
        try:
            line = self.format(record) + self.terminator
            if self._written + len(line.encode()) > self._limit:
                line = _NOTICE.format(limit=self._limit) + self.terminator
                self._written = self._limit
            else:
                self._written += len(line.encode())
            self.stream.write(line)
            self.flush()
        except Exception:  # noqa: BLE001 - logging's own contract: report, never raise
            self.handleError(record)


def configure_logging(stream: TextIO | None = None) -> None:
    """Send the root logger to ``stream`` (stderr) through a bounded handler.

    Like :func:`logging.basicConfig`, does nothing when the root logger already
    has a handler.
    """
    root = logging.getLogger()
    if root.handlers:
        return
    handler = BoundedStreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
