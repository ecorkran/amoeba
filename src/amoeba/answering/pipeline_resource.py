"""Locate a pipeline file shipped inside an Amoeba package (slices 140 and 180)."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def shipped_pipeline_path(package: str, file_name: str, label: str) -> Path:
    """Absolute path of ``file_name`` inside ``package``.

    Raises:
        FileNotFoundError: Naming ``label`` and the path, when the file is not in
            the package (a broken install).
    """
    resource = resources.files(package).joinpath(file_name)
    path = Path(str(resource))
    if not path.is_file():
        raise FileNotFoundError(f"{label} pipeline file is missing: {path}")
    return path.resolve()
