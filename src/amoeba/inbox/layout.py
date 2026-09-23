"""The inbox directory layout and filename scheme, each defined exactly once.

Under the supervisor directory::

    inbox/tmp/         files being written; never read by the apply loop
    inbox/new/         complete submissions awaiting apply
    inbox/quarantine/  submissions that could not be attributed, + .reason.json
    inbox/failed/      attributed submissions whose apply kept failing,
                       + .attempts.json

A submission file is named ``{submitted_at_ns:020d}-{submission_id}.json``. The
timestamp prefix only orders the drain; it is **not** the authoritative order,
which the receiver assigns at apply (D4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

INBOX_DIR_NAME: Final = "inbox"
TMP_DIR_NAME: Final = "tmp"
NEW_DIR_NAME: Final = "new"
QUARANTINE_DIR_NAME: Final = "quarantine"
FAILED_DIR_NAME: Final = "failed"

SUBMISSION_SUFFIX: Final = ".json"
#: Beside a quarantined file: why it could not be attributed.
REASON_SIDECAR_SUFFIX: Final = ".reason.json"
#: Beside a file in ``new/`` or ``failed/``: how many applies have failed.
ATTEMPTS_SIDECAR_SUFFIX: Final = ".attempts.json"

_SIDECAR_SUFFIXES: Final = (REASON_SIDECAR_SUFFIX, ATTEMPTS_SIDECAR_SUFFIX)

#: Width of the zero-padded nanosecond prefix, so names sort as timestamps.
_TIMESTAMP_WIDTH: Final = 20


def inbox_dir(store_dir: Path) -> Path:
    return store_dir / INBOX_DIR_NAME


def tmp_dir(store_dir: Path) -> Path:
    return inbox_dir(store_dir) / TMP_DIR_NAME


def new_dir(store_dir: Path) -> Path:
    return inbox_dir(store_dir) / NEW_DIR_NAME


def quarantine_dir(store_dir: Path) -> Path:
    return inbox_dir(store_dir) / QUARANTINE_DIR_NAME


def failed_dir(store_dir: Path) -> Path:
    return inbox_dir(store_dir) / FAILED_DIR_NAME


def submission_filename(submitted_at_ns: int, submission_id: str) -> str:
    """The file name for one submission. The caller has validated the id."""
    return f"{submitted_at_ns:0{_TIMESTAMP_WIDTH}d}-{submission_id}{SUBMISSION_SUFFIX}"


def reason_sidecar(submission_file: Path) -> Path:
    """The ``.reason.json`` beside a quarantined file."""
    return submission_file.with_name(submission_file.name + REASON_SIDECAR_SUFFIX)


def attempts_sidecar(submission_file: Path) -> Path:
    """The ``.attempts.json`` beside a file in ``new/`` or ``failed/``."""
    return submission_file.with_name(submission_file.name + ATTEMPTS_SIDECAR_SUFFIX)


def is_submission_file(path: Path) -> bool:
    """A submission file, as opposed to a sidecar or anything else."""
    return (
        path.is_file()
        and path.name.endswith(SUBMISSION_SUFFIX)
        and not path.name.endswith(_SIDECAR_SUFFIXES)
    )


def submission_files(directory: Path) -> list[Path]:
    """Submission files in a directory, in drain order. Empty if absent."""
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if is_submission_file(path))
