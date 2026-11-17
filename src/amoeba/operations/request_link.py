"""The link from a paused question to a request its repo sent (slice 242, D1).

A question is held on a request only when its text carries the marker
``amoeba-request: <id>`` and the id is exactly a request the question's member sent.
The match is on an exact id, never a judgment about the text. Pure: the caller
supplies ``resolve``, which says whether a candidate id is such a request, so this
module reads no store.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

#: The marker's two words; ``-``, ``_`` or a space may sit between them.
MARKER_WORDS: Final = ("amoeba", "request")
#: The characters of a request id (240 D2).
REQUEST_ID_CHARACTERS: Final = "A-Za-z0-9._-"
#: Quote and bracket characters an agent may put around the id.
_ID_WRAPPERS: Final = "\"'`[](){}<>"
#: The marker, its ``:`` or ``=``, then optional spaces and wrappers, then the id.
#: Squadron joins a reply's lines with spaces, so the marker is found anywhere.
_MARKER: Final = re.compile(
    rf"{MARKER_WORDS[0]}[-_ ]{MARKER_WORDS[1]}\s*[:=][\s{re.escape(_ID_WRAPPERS)}]*"
    rf"([{REQUEST_ID_CHARACTERS}]*)",
    re.IGNORECASE,
)
#: Sentence punctuation that is also an id character.
_TRAILING_DOT: Final = "."


@dataclass(frozen=True)
class NoLink:
    """No marker: the question takes the ordinary answering path."""


@dataclass(frozen=True)
class Link:
    """Exactly one distinct request id resolved."""

    request_id: str


@dataclass(frozen=True)
class BadLink:
    """A marker resolved to no request, or the markers named two or more."""

    detail: str


type LinkResult = NoLink | Link | BadLink


def find_request_link(question: str, resolve: Callable[[str], bool]) -> LinkResult:
    """The link the question's markers make.

    ``resolve(candidate)`` is True when ``candidate`` is a ``request`` row sent by the
    question's member. A run of id characters ending in ``.`` is tried as written
    and without its trailing dots, since ``.`` also ends a sentence; one marker names
    the first of those that resolves, so it never counts as two requests.
    """
    resolved: list[str] = []
    unresolved: list[str] = []
    for match in _MARKER.finditer(question):
        found = next((c for c in _candidates(match.group(1)) if resolve(c)), None)
        if found is not None:
            resolved.append(found)
        else:
            unresolved.append(match.group(1))
    if not resolved and not unresolved:
        return NoLink()
    distinct = list(dict.fromkeys(resolved))
    if unresolved:
        named = ", ".join(repr(text) for text in unresolved)
        return BadLink(
            f"the amoeba-request marker names {named}, which is not a request "
            "this project sent"
        )
    if len(distinct) > 1:
        return BadLink(
            f"the amoeba-request markers name {len(distinct)} requests "
            f"({', '.join(distinct)}); a question waits on exactly one"
        )
    return Link(distinct[0])


def _candidates(run: str) -> list[str]:
    """The ids one marker may mean: as written, and without trailing dots."""
    stripped = run.rstrip(_TRAILING_DOT)
    return [text for text in dict.fromkeys((run, stripped)) if text]
