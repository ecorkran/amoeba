"""The built wheel ships the slice-writing pipeline file, usable once installed.

This runs ``uv build`` in the default tier, as the answering pipeline's wheel test
does: the default tier needs ``uv`` and a working hatchling build, a cost accepted
because a pipeline file missing from the wheel only fails in an installed Amoeba.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

from amoeba.runner.request_run.pipeline_file import PIPELINE_FILE_NAME

REPOSITORY_ROOT = Path(__file__).parents[3]
BUILD_TIMEOUT_SECONDS = 300
RUN_TIMEOUT_SECONDS = 60
PACKAGED_NAME = f"amoeba/runner/request_run/{PIPELINE_FILE_NAME}"
PRINT_PATH = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from amoeba.runner.request_run.pipeline_file import "
    "slice_writing_pipeline_path; "
    "print(slice_writing_pipeline_path())"
)


def test_wheel_lists_and_serves_the_pipeline_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with zipfile.ZipFile(wheels[0]) as wheel:
        assert PACKAGED_NAME in wheel.namelist()
        wheel.extractall(extracted)
    # -I and an explicit first sys.path entry: the source checkout cannot answer.
    result = subprocess.run(
        [sys.executable, "-I", "-c", PRINT_PATH, str(extracted)],
        check=True,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        cwd=tmp_path,
        timeout=RUN_TIMEOUT_SECONDS,
    )
    served = Path(result.stdout.strip())
    assert served.is_file()
    assert served.resolve().is_relative_to(extracted.resolve())
