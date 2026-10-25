"""The shipped routing table is in the built wheel, not only in a source checkout."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHIPPED_TABLE = "amoeba/runner/routing/tables/default.yaml"
BUILD_TIMEOUT_SECONDS = 180


def test_the_wheel_contains_the_default_table(tmp_path: Path) -> None:
    built = subprocess.run(
        ["uv", "build", "--wheel", "--offline", "--out-dir", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=BUILD_TIMEOUT_SECONDS,
        check=False,
    )
    if built.returncode != 0:
        # The build backend (hatchling) is not a dev dependency. Offline, uv can
        # only use a cached copy; without one this is the environment's limit,
        # not a defect. Any other failure is a real build failure.
        if "hatchling" in built.stderr:
            pytest.skip(f"hatchling is not cached offline: {built.stderr.strip()}")
        pytest.fail(f"uv build failed:\n{built.stderr}")
    [wheel] = tmp_path.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        assert SHIPPED_TABLE in archive.namelist()
