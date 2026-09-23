"""Write a file so that it is either absent or complete and durable.

The one tmp-and-rename in the inbox. ``submit()`` writes submissions with it,
and the tenant writes its ``.attempts.json`` counters with it, so both carry
the same guarantee: a reader of the final directory never sees a partial file.

The order is the guarantee, and it is fixed: write to ``tmp``, fsync the file,
rename into place, fsync the destination directory. Without the file fsync the
rename can be durable before the content is; without the directory fsync the
rename itself can be lost. What this buys is fsync-durability on a POSIX
filesystem — no more is claimed.
"""

from __future__ import annotations

import os
from pathlib import Path


def fsync_directory(directory: Path) -> None:
    """Make a directory's entries — a rename into it — durable."""
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_durably(content: str, *, tmp_path: Path, final_path: Path) -> None:
    """Write ``content`` to ``final_path`` by way of ``tmp_path``.

    ``tmp_path`` must be on the same filesystem as ``final_path`` so the rename
    is atomic; the inbox keeps both under one directory tree.

    Raises:
        OSError: On any write, fsync, or rename failure. ``tmp_path`` is
            removed before the error propagates, and ``final_path`` is never
            touched unless the rename succeeded.
    """
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(final_path)
    except OSError:
        # Removed so a failed write leaves nothing behind; the caller gets the
        # original error. missing_ok covers a failure before the file existed.
        tmp_path.unlink(missing_ok=True)
        raise

    fsync_directory(final_path.parent)
