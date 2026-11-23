"""Write a file so a reader sees the old one or the new one, never half of it.

Used by every file the client and the hub save under a fixed name: the client file,
the pinned certificate, and the hub's certificate and key (slice 260).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

#: The one temporary name a write uses; a crash leaves at most this file, which the
#: next write of the same path replaces.
TEMPORARY_SUFFIX: Final = ".tmp"
#: The mode of a public file (a certificate).
PUBLIC_FILE_MODE: Final = 0o644
#: The mode of a file that holds a credential (the client file, the hub's key).
PRIVATE_FILE_MODE: Final = 0o600


def write_through_rename(path: Path, data: bytes, mode: int) -> None:
    """Write ``data`` to ``path`` with ``mode`` through ``<path>.tmp`` and a rename.

    The parent directory is made when missing. The mode is set before the data is
    written, so a leftover temporary file with another mode never holds a credential
    that anyone else can read.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + TEMPORARY_SUFFIX)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(descriptor, "wb") as handle:
        os.fchmod(handle.fileno(), mode)
        handle.write(data)
    temporary.replace(path)
