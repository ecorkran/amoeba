"""Live validation of the shipped slice-writing file by the real ``sq`` (Task 9.2).

No model is called and nothing is spent: ``--validate --strict`` reads the file and
exits. It proves the shipped Squadron accepts the commit step and the two options,
and that ``--strict`` still rejects a key the step does not read.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from amoeba.process import SQ_EXECUTABLE
from amoeba.runner.request_run.pipeline_file import (
    COMMIT_STEP,
    IO_DIRECTORY_OPTION,
    MAX_COST_OPTION,
    PROBE_MAX_COST_USD,
    slice_writing_pipeline_path,
)

SQ_TIMEOUT_SECONDS = 60
UNKNOWN_STEP_KEY = "unknown_step_key_for_test"


def _validate(pipeline: Path, scratch: Path) -> subprocess.CompletedProcess[str]:
    """Run the probe's argv on ``pipeline`` from an empty directory."""
    io_directory = scratch / "io"
    io_directory.mkdir()
    working_directory = scratch / "cwd"
    working_directory.mkdir()
    return subprocess.run(
        [
            SQ_EXECUTABLE,
            "run",
            str(pipeline),
            "--validate",
            "--strict",
            IO_DIRECTORY_OPTION,
            str(io_directory),
            MAX_COST_OPTION,
            str(PROBE_MAX_COST_USD),
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        timeout=SQ_TIMEOUT_SECONDS,
        check=False,
    )


def test_shipped_file_validates_strictly(tmp_path: Path) -> None:
    completed = _validate(slice_writing_pipeline_path(), tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_unknown_step_key_is_rejected(tmp_path: Path) -> None:
    text = slice_writing_pipeline_path().read_text(encoding="utf-8")
    anchor = f"      name: {COMMIT_STEP}\n"
    assert text.count(anchor) == 1, "the commit step's name line was not found"
    altered = text.replace(anchor, f"{anchor}      {UNKNOWN_STEP_KEY}: 1\n")
    pipeline = tmp_path / "altered.yaml"
    pipeline.write_text(altered, encoding="utf-8")
    completed = _validate(pipeline, tmp_path)
    assert completed.returncode != 0
    assert UNKNOWN_STEP_KEY in completed.stdout + completed.stderr
