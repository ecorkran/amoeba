"""Plain-text helpers shared by every renderer (slice 229, D2). Pure: no I/O.

Prose (a question, an answer, a reason) is cut to :data:`COLUMNS` columns with ``…``
and kept on one line; the full text is in ``-j``. Commands and paths are never cut:
they sit on their own indented line so they can be pasted.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Final

#: The widest a line of prose may be.
COLUMNS: Final = 100
ELLIPSIS: Final = "…"
INDENT: Final = "  "
#: Between the parts of a one-line summary.
SEPARATOR: Final = " · "
#: The word for "no rules" and for "no members" in a list.
NONE: Final = "none"
DEFAULT_RULES_LABEL: Final = "default"

_SECONDS_PER_MINUTE: Final = 60
_MINUTES_PER_HOUR: Final = 60
_HOURS_PER_DAY: Final = 24


def one_line(text: str) -> str:
    """``text`` with every run of whitespace, newlines included, as one space."""
    return " ".join(text.split())


def cut(text: str, columns: int = COLUMNS) -> str:
    """``text`` on one line, ending in ``…`` when it was longer than ``columns``."""
    line = one_line(text)
    if len(line) <= columns:
        return line
    return line[: columns - len(ELLIPSIS)].rstrip() + ELLIPSIS


def prose_line(prefix: str, text: str, columns: int = COLUMNS) -> str:
    """``prefix`` then ``text``, the whole line at most ``columns`` wide."""
    return prefix + cut(text, max(columns - len(prefix), len(ELLIPSIS) + 1))


def was_cut(prefix: str, text: str, columns: int = COLUMNS) -> bool:
    """Whether :func:`prose_line` would cut ``text`` after ``prefix``."""
    return len(prefix) + len(one_line(text)) > max(
        columns, len(prefix) + len(ELLIPSIS) + 1
    )


def command_line(text: str, depth: int = 2) -> str:
    """A command or path on its own line, indented ``depth`` levels, never cut."""
    return INDENT * depth + text.strip()


def indented(line: str, depth: int = 1) -> str:
    return INDENT * depth + line


def how_long(since: datetime, now: datetime) -> str:
    """A short age: ``3d 4h``, ``5h 12m``, ``7m`` or ``<1m``."""
    minutes = max(int((now - since).total_seconds()), 0) // _SECONDS_PER_MINUTE
    hours, minutes = divmod(minutes, _MINUTES_PER_HOUR)
    days, hours = divmod(hours, _HOURS_PER_DAY)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m" if minutes else "<1m"


def rules_text(entries: Sequence[str], *, default: bool) -> str:
    """A member's rules: ``default (A, B)`` for the config default, else the named
    entries, or ``none`` when there are none."""
    joined = ", ".join(entries)
    if default:
        return f"{DEFAULT_RULES_LABEL} ({joined})"
    return joined or NONE
