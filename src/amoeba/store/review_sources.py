"""Where review files come from (D6 of slice 106).

``ReviewSource.poll()`` is the one interface the detection tenant reads.
``DirectoryReviewSource`` is the only implementation today. When Squadron ships
a review-completed event (dependency S8), an event source implements the same
method and nothing downstream — the tenant, the ledger, attribution, the feed —
changes.

The source handles file-level races itself, so the tenant only ever sees whole
files it could read. It never writes into the directory and never resolves
symlinks.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

logger = logging.getLogger(__name__)

#: Squadron writes reviews as markdown at the top of the reviews directory.
REVIEW_FILE_SUFFIX: Final = ".md"


class ReviewDirectoryUnavailableError(Exception):
    """A watched directory could not be listed. Never reported as empty."""


@dataclass(frozen=True)
class DetectedFile:
    """One settled review file and the exact bytes read from it."""

    path: Path
    content: bytes
    observed_at: datetime


class ReviewSource(Protocol):
    """Yields review files that are complete and ready to examine."""

    def poll(self) -> Sequence[DetectedFile]: ...


def list_review_files(directory: Path) -> list[Path]:
    """The one listing rule: regular, top-level ``*.md`` files, sorted by name.

    Non-recursive: Squadron writes to the top level, and ``archive/`` holds
    rounds already seen.

    Raises:
        ReviewDirectoryUnavailableError: The directory cannot be listed.
    """
    try:
        entries = list(directory.iterdir())
    except OSError as error:
        # Specific: missing, not a directory, or unreadable. Typed so no caller
        # mistakes an unreachable directory for one with no reviews.
        raise ReviewDirectoryUnavailableError(
            f"cannot list {directory}: {error}"
        ) from error
    return sorted(
        entry
        for entry in entries
        if entry.suffix == REVIEW_FILE_SUFFIX and entry.is_file()
    )


type Signature = tuple[int, int]


class DirectoryReviewSource:
    """Polls one directory. A file is returned once it has settled.

    Settled means its ``(size, mtime_ns)`` is unchanged since the previous
    poll; a first sighting is remembered, not returned. A settled file is
    returned **once per signature**: an unchanged file is not re-read or
    re-hashed on later polls, so a scan costs one ``stat`` per file. A new
    source (a restart) returns every settled file once more; the tenant's
    ledger check skips the ones already examined.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._signatures: dict[Path, Signature] = {}
        self._delivered: dict[Path, Signature] = {}
        self._unreadable: set[Path] = set()

    def poll(self) -> Sequence[DetectedFile]:
        """Settled files with their bytes.

        Raises:
            ReviewDirectoryUnavailableError: The directory cannot be listed.
        """
        listed = list_review_files(self._directory)
        for forgotten in set(self._signatures) - set(listed):
            del self._signatures[forgotten]
            self._delivered.pop(forgotten, None)

        settled: list[DetectedFile] = []
        for path in listed:
            detected = self._examine(path)
            if detected is not None:
                settled.append(detected)
        return settled

    def _examine(self, path: Path) -> DetectedFile | None:
        try:
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            previous = self._signatures.get(path)
            self._signatures[path] = signature
            if previous != signature or self._delivered.get(path) == signature:
                return None
            content = path.read_bytes()
        except FileNotFoundError:
            # Specific: gone between listing and stat or read. A file that is
            # gone is not a review; if it returns it settles from scratch.
            self._signatures.pop(path, None)
            self._delivered.pop(path, None)
            return None
        except PermissionError:
            # Specific: nothing was examined, so no ledger row. Warned once
            # until the file becomes readable.
            if path not in self._unreadable:
                logger.warning("review file %s is unreadable; skipping it", path)
                self._unreadable.add(path)
            return None
        self._unreadable.discard(path)
        self._delivered[path] = signature
        return DetectedFile(path=path, content=content, observed_at=datetime.now(UTC))
