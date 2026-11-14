"""Drop rule sections an earlier rules file already holds (slice 229, D9).

Repos often keep one set of rules in two files (an ``AGENTS.md`` that repeats
``CLAUDE.md``). A rule passage whose text equals a passage of an earlier rules file
is dropped and the earlier file keeps it, so a citation names that file. Plan and
program passages are never dropped. A section edited in one file but not the other is
two different passages and both stay. Only earlier files count: a repeated section
inside one file stays, because nothing there says the author meant it as a copy.
"""

from __future__ import annotations

from collections.abc import Sequence


class RuleDeduper:
    """The rule passages read so far; one instance per selection, files in order."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def new_pieces(self, *, is_rule: bool, pieces: Sequence[str]) -> tuple[str, ...]:
        """The pieces of the next file that earlier files did not already hold.

        A file that is not a rule file is returned whole and does not count as seen.
        """
        if not is_rule:
            return tuple(pieces)
        fresh = tuple(piece for piece in pieces if piece not in self._seen)
        self._seen.update(pieces)
        return fresh
