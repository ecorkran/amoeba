"""The hub's rotating log (slice 260, D16).

One ``RotatingFileHandler`` on the root logger, so the libraries' own messages that a
peer can cause without a token (``uvicorn.error``, ``asyncio``) land in the file too,
and Python's last-resort stderr handler is never used. The serving process logs to
this file only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

LOG_LEVEL: Final = logging.INFO
LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s: %(message)s"
#: The ``machine`` field of a refusal line when the token was not good.
NO_MACHINE: Final = "-"


def start_hub_log(path: Path, max_bytes: int, kept: int) -> RotatingFileHandler:
    """Put one rotating handler on the root logger and return it.

    ``kept`` counts the current file, so the rotation keeps ``kept - 1`` old ones.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=kept - 1, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(LOG_LEVEL)
    return handler


def refusal_line(time: datetime, peer: str, code: str, machine: str | None) -> str:
    """One refused call as one line (D16): the hub's time, the caller's address, the
    code, and the machine's name when the token was good. Never the token, the body
    or the document."""
    return (
        f"refused {time.isoformat()} peer={peer} code={code} "
        f"machine={NO_MACHINE if machine is None else machine}"
    )
