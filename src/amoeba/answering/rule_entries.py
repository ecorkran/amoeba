"""Pick the rules files a choice names, with the optional-entry handling (slice 229).

A named choice fails the whole selection when an entry matches nothing. An optional
choice (the config default) skips an entry that matches nothing, and declines
``sources_missing`` only when every entry was skipped. For an entry in a
subdirectory, whether the directory exists is read with ``git ls-tree``: empty
output from a successful call means absent, and a failed call is
``sources_unreadable``, so "absent" never comes from an error (D8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from amoeba.answering.passages import (
    PassageKind,
    SourcesProblem,
    SourcesProblemKind,
    match_rules_entry,
)
from amoeba.answering.settings import RulesChoice


@dataclass(frozen=True)
class SelectedFile:
    path: str
    kind: PassageKind
    #: Chosen through an optional (config default) entry; import following reads
    #: this to decide whether a missing import is skipped (D10).
    optional: bool = False


class DirectoryListings(Protocol):
    """What entry selection needs from the pinned commit's directories."""

    def of(self, directory: str, context: str) -> tuple[str, ...] | SourcesProblem:
        """File names in ``directory``; a failure is prefixed with ``context``."""
        ...

    def exists(self, directory: str, context: str) -> bool | SourcesProblem:
        """Whether ``directory`` is present; only a clean ``ls-tree`` says no."""
        ...


def parent_and_name(entry: str) -> tuple[str, str]:
    parent, _, name = entry.rpartition("/")
    return parent, name


def select_rules(
    listings: DirectoryListings, rules: RulesChoice
) -> tuple[SelectedFile, ...] | SourcesProblem:
    """The rule files the choice names, in entry order.

    Returns ``sources_missing`` when a named entry matches nothing, or when an
    optional choice matched nothing at all.
    """
    chosen: list[SelectedFile] = []
    for entry in rules.entries:
        found = _select_entry(listings, entry, rules.optional)
        if isinstance(found, SourcesProblem):
            return found
        chosen.extend(found)
    if rules.optional and not chosen:
        return SourcesProblem(
            SourcesProblemKind.MISSING,
            f"no rules file found; tried: {', '.join(rules.entries)}",
        )
    return tuple(chosen)


def _select_entry(
    listings: DirectoryListings, entry: str, optional: bool
) -> tuple[SelectedFile, ...] | SourcesProblem:
    parent, _ = parent_and_name(entry)
    context = f"rules entry {entry!r}"
    # ``git show`` fails on an absent directory, so presence is read with ``ls-tree``
    # first: absence is then missing (named) or skipped (optional), never unreadable.
    if parent:
        present = listings.exists(parent, context)
        if isinstance(present, SourcesProblem):
            return present
        if not present:
            return _no_match(entry, optional)
    names = listings.of(parent, context)
    if not isinstance(names, tuple):
        return names
    matched = match_rules_entry(entry, names)
    if not matched:
        return _no_match(entry, optional)
    prefix = f"{parent}/" if parent else ""
    return tuple(
        SelectedFile(prefix + name, PassageKind.RULE, optional=optional)
        for name in matched
    )


def _no_match(entry: str, optional: bool) -> tuple[SelectedFile, ...] | SourcesProblem:
    """An entry that names no file: skipped when optional, else the selection fails."""
    if optional:
        return ()
    return SourcesProblem(
        SourcesProblemKind.MISSING, f"rules entry {entry!r} matches no file"
    )
