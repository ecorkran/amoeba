"""Which projects have a store in a supervisor directory.

In ``amoeba.store`` so the resident process and the read-only inspection path
share one scan without either importing the other.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.store.paths import STORE_FILE_SUFFIX


def discover_project_ids(store_dir: Path) -> list[str]:
    """Project ids having a store in the supervisor directory.

    An absent directory yields no projects rather than an error: a supervisor
    that has never run is a valid, empty state — which is what
    ``amoeba inspect projects`` reports against a fresh directory.
    """
    if not store_dir.is_dir():
        return []
    return sorted(
        path.name[: -len(STORE_FILE_SUFFIX)]
        for path in store_dir.glob(f"*{STORE_FILE_SUFFIX}")
        if path.is_file()
    )
