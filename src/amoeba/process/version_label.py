"""Capturing an upstream tool's ``--version`` as an opaque provenance label.

One routine serves every executable (``cf``, ``sq``). It never raises: a
failure is recorded as :data:`VERSION_UNAVAILABLE`. The label is stored and
never compared, parsed, or ordered.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence
from typing import Final

from amoeba.process.sq_outcome import SQ_EXECUTABLE

logger = logging.getLogger(__name__)

#: Recorded in place of a version label when the executable cannot report one.
#: An explicit, obviously-non-version marker rather than an empty string or a
#: plausible-looking number.
VERSION_UNAVAILABLE: Final = "unavailable"

#: The argument every upstream executable takes to print its version.
VERSION_ARGS: Final = ("--version",)


def capture_version_label(
    executable: str, timeout_seconds: float, args: Sequence[str] = VERSION_ARGS
) -> str:
    """Run ``executable --version`` once and return its trimmed stdout.

    Returns:
        The label, or :data:`VERSION_UNAVAILABLE` when the executable is
        missing, times out, exits non-zero, or prints nothing.
    """
    try:
        completed = subprocess.run(
            (executable, *args),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        # Specific: the executable is missing from PATH, or the call timed out.
        # Provenance capture never fails the caller, so this is recorded
        # rather than propagated.
        logger.warning("cannot capture %s version label", executable, exc_info=True)
        return VERSION_UNAVAILABLE

    if completed.returncode != 0:
        logger.warning(
            "%s --version exited %d; recording the label as unavailable",
            executable,
            completed.returncode,
        )
        return VERSION_UNAVAILABLE

    label = completed.stdout.strip()
    return label if label else VERSION_UNAVAILABLE


def capture_sq_version_label(timeout_seconds: float) -> str:
    """``sq --version`` as a label. Called once, at process start-up."""
    return capture_version_label(SQ_EXECUTABLE, timeout_seconds)
