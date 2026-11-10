"""The built wheel ships the store's migrations and the ``amoeba`` entry point."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]
BUILD_TIMEOUT_SECONDS = 300
BASELINE_MIGRATION = "amoeba/store/schema/001_baseline.sql"
ENTRY_POINT = "amoeba = amoeba.cli.main:main"


def test_wheel_contains_the_baseline_migration_and_the_entry_point(
    tmp_path: Path,
) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = wheel.namelist()
        entry_points = next(
            wheel.read(name).decode("utf-8")
            for name in names
            if name.endswith("entry_points.txt")
        )
    assert BASELINE_MIGRATION in names
    assert ENTRY_POINT in entry_points
