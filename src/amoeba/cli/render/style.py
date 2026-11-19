"""Terminal color for the text views: a few words, never boxes. Pure: no I/O.

Color is on only when a person reads a terminal that wants it (:func:`painter_for`);
``-j``, a pipe and a file always get the plain text. Each tone is one ANSI code, so
removing the escapes gives back exactly the plain text.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TextIO

RESET: Final = "\x1b[0m"
#: The environment that turns color off (https://no-color.org, and ``dumb`` terminals).
NO_COLOR_VARIABLE: Final = "NO_COLOR"
TERM_VARIABLE: Final = "TERM"
DUMB_TERMINAL: Final = "dumb"


class Tone(StrEnum):
    """What a painted word means; the value is its ANSI code."""

    #: A section heading, for fast scanning.
    HEADING = "1;36"
    #: A section that wants the PM's eye.
    ATTENTION = "1;33"
    #: Nothing is wrong.
    OK = "32"


@dataclass(frozen=True)
class Painter:
    """Wraps text in a tone's color, or returns it as given when ``enabled`` is off."""

    enabled: bool

    def __call__(self, text: str, tone: Tone) -> str:
        if not self.enabled:
            return text
        return f"\x1b[{tone.value}m{text}{RESET}"


PLAIN: Final = Painter(enabled=False)


def painter_for(stream: TextIO, environ: Mapping[str, str]) -> Painter:
    """Color for ``stream`` only if it is a terminal and ``environ`` does not refuse."""
    if environ.get(NO_COLOR_VARIABLE):
        return PLAIN
    if environ.get(TERM_VARIABLE) == DUMB_TERMINAL:
        return PLAIN
    return Painter(enabled=stream.isatty())
