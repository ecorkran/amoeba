"""The one atomic write (slice 260)."""

from __future__ import annotations

import stat
from pathlib import Path

from amoeba.wire.atomic_file import (
    PRIVATE_FILE_MODE,
    PUBLIC_FILE_MODE,
    TEMPORARY_SUFFIX,
    write_through_rename,
)


def test_it_writes_the_data_with_the_mode_and_leaves_no_temporary_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "made" / "credential"

    write_through_rename(path, b"secret", PRIVATE_FILE_MODE)

    assert path.read_bytes() == b"secret"
    assert stat.S_IMODE(path.stat().st_mode) == PRIVATE_FILE_MODE
    assert [p.name for p in path.parent.iterdir()] == ["credential"]


def test_it_replaces_an_existing_file_and_a_leftover_temporary_with_another_mode(
    tmp_path: Path,
) -> None:
    path = tmp_path / "credential"
    path.write_bytes(b"old")
    leftover = path.with_name(path.name + TEMPORARY_SUFFIX)
    leftover.write_bytes(b"half")
    leftover.chmod(PUBLIC_FILE_MODE)

    write_through_rename(path, b"new", PRIVATE_FILE_MODE)

    assert path.read_bytes() == b"new"
    assert stat.S_IMODE(path.stat().st_mode) == PRIVATE_FILE_MODE
    assert not leftover.exists()
