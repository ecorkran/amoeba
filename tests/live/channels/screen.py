"""The pseudo-terminal's output as searchable text (slice 241, D10).

Claude Code draws with Ink, which positions words with cursor moves rather than
spaces. Matching works on the meaning, not the layout: every cursor move becomes a
space, every other escape sequence is dropped, and runs of whitespace collapse to one
space on both sides of a comparison.
"""

from __future__ import annotations

import re
import threading
from typing import Final

#: Cursor moves (forward, column, position) stand where a gap was drawn.
_CURSOR_MOVE: Final = re.compile(r"\x1b\[[0-9;]*[CGHf]")
#: Every other control sequence: CSI, OSC, charset selection, keypad modes.
_ESCAPE: Final = re.compile(
    r"\x1b\[[0-9;?<>=]*[ -/]*[@-~]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|\x1b[()][0-9A-Za-z]"
    r"|\x1b[=>78]"
)
_WHITESPACE: Final = re.compile(r"\s+")
#: How much of the end of the output a failure message shows.
LAST_SCREEN_CHARACTERS: Final = 4000


def plain_text(raw: str) -> str:
    """``raw`` terminal output with escapes removed and cursor moves as spaces."""
    return _ESCAPE.sub("", _CURSOR_MOVE.sub(" ", raw))


def normalized(text: str) -> str:
    """``text`` with every whitespace run collapsed to one space."""
    return _WHITESPACE.sub(" ", text)


class ScreenLog:
    """Everything the terminal printed, appended by a reader thread.

    The reader thread appends and the test thread reads; ``_lock`` publishes each
    append to the reader of ``text_since``.
    """

    def __init__(self) -> None:
        self._raw: list[str] = []
        self._length = 0
        self._lock = threading.Lock()

    def append(self, chunk: str) -> None:
        with self._lock:
            self._raw.append(chunk)
            self._length += len(chunk)

    def mark(self) -> int:
        """A position; ``text_since`` from it shows only what was printed later."""
        with self._lock:
            return self._length

    def text_since(self, position: int) -> str:
        """The normalized plain text printed from ``position`` on."""
        with self._lock:
            raw = "".join(self._raw)
        return normalized(plain_text(raw[position:]))

    def last_screen(self) -> str:
        """The end of the output as plain text, for failure messages."""
        with self._lock:
            raw = "".join(self._raw)
        return plain_text(raw)[-LAST_SCREEN_CHARACTERS:]
