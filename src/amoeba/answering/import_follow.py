"""Follow ``@path`` imports of a rules file (slice 229, D10).

Each import resolves against the importing file's directory, must stay inside the
repository, and is read at the pinned commit as a rule file placed directly after its
importer, which may import in turn. Limits, each with its result:

- depth: more than :data:`IMPORT_DEPTH` imports deep is ``sources_unreadable``, the
  detail giving the chain;
- a file already read is not read twice, with no error (so a cycle ends);
- an import that resolves outside the repository is ``sources_unreadable``, whichever
  kind of entry began the chain;
- a missing target is skipped when the chain began at an optional (config default)
  entry, and is ``sources_missing`` when it began at a named one.

Absence comes from a directory listing, never from a failed read.
"""

from __future__ import annotations

import posixpath
from typing import Final, Protocol

from amoeba.answering.passages import (
    SourceFile,
    SourcesProblem,
    SourcesProblemKind,
    unreadable,
)
from amoeba.answering.rule_entries import DirectoryListings, parent_and_name
from amoeba.answering.rule_imports import rule_imports

#: Most imports deep a chain may go; the entry file itself is depth 0.
IMPORT_DEPTH: Final = 3
_CHAIN_ARROW: Final = " -> "


class ImportHost(Protocol):
    """What following imports needs from the read that is under way."""

    @property
    def listings(self) -> DirectoryListings: ...

    def has_read(self, path: str) -> bool:
        """Whether the file was already read in this selection."""
        ...

    def read_rule(self, path: str) -> SourceFile | SourcesProblem:
        """Read ``path`` as a rule file and count it; the next file follows it."""
        ...


def follow_imports(
    host: ImportHost,
    importer: SourceFile,
    *,
    optional: bool,
    chain: tuple[str, ...] = (),
) -> SourcesProblem | None:
    """Read the imports of ``importer`` (and theirs), or the problem that stops it.

    Args:
        host: The selection read.
        importer: A rule file already read.
        optional: The chain began at a config default entry.
        chain: The files from the entry down to, not including, ``importer``.
    """
    here = (*chain, importer.path)
    for written in rule_imports(importer.text):
        target = _resolve(importer.path, written)
        if target is None:
            return unreadable(
                f"import @{written} in {importer.path} resolves outside the repository"
            )
        if host.has_read(target):
            continue
        if len(here) > IMPORT_DEPTH:
            return unreadable(
                f"imports are more than {IMPORT_DEPTH} deep: "
                + _CHAIN_ARROW.join((*here, target))
            )
        problem = _read_import(host, importer, written, target, optional, here)
        if problem is not None:
            return problem
    return None


def _read_import(  # noqa: PLR0913 - one import's identity and its chain
    host: ImportHost,
    importer: SourceFile,
    written: str,
    target: str,
    optional: bool,
    chain: tuple[str, ...],
) -> SourcesProblem | None:
    present = _is_present(
        host.listings, target, f"import @{written} in {importer.path}"
    )
    if isinstance(present, SourcesProblem):
        return present
    if not present:
        if optional:
            return None
        return SourcesProblem(
            SourcesProblemKind.MISSING,
            f"import @{written} in {importer.path} matches no file",
        )
    read = host.read_rule(target)
    if not isinstance(read, SourceFile):
        return read
    return follow_imports(host, read, optional=optional, chain=chain)


def _resolve(importer_path: str, written: str) -> str | None:
    """The repo-relative path of an import, or ``None`` when it leaves the repo."""
    joined = posixpath.normpath(
        posixpath.join(posixpath.dirname(importer_path), written)
    )
    if joined == ".." or joined.startswith("../"):
        return None
    return joined


def _is_present(
    listings: DirectoryListings, path: str, context: str
) -> bool | SourcesProblem:
    """Whether the file is in its directory at the commit, from listings only."""
    parent, name = parent_and_name(path)
    if parent:
        exists = listings.exists(parent, context)
        if isinstance(exists, SourcesProblem) or not exists:
            return exists
    names = listings.of(parent, context)
    if isinstance(names, SourcesProblem):
        return names
    return name in names
