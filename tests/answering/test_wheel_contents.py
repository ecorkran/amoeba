"""The built wheel ships the answering pipeline file."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

from amoeba.answering.pipeline_file import PIPELINE_FILE_NAME

REPOSITORY_ROOT = Path(__file__).parents[2]
BUILD_TIMEOUT_SECONDS = 300


def test_wheel_lists_the_pipeline_file(tmp_path: Path) -> None:
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
    assert f"amoeba/answering/{PIPELINE_FILE_NAME}" in names
