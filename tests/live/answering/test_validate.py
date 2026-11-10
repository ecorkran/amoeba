"""``sq run <answering.yaml> --validate`` accepts the shipped pipeline.

Real ``sq`` is not on the default CI image, so this runs with the live tier
(``uv run pytest tests/live``). It starts nothing and spends nothing.
"""

from __future__ import annotations

import subprocess

from amoeba.answering.pipeline_file import (
    ANSWER_MODEL_PARAM,
    CHECK_MODEL_PARAM,
    answering_pipeline_path,
)
from amoeba.upstream.squadron.run_outcome import SQ_EXECUTABLE

VALIDATE_TIMEOUT_SECONDS = 60


def test_sq_validates_the_shipped_answering_pipeline(live_settings: object) -> None:
    del live_settings  # only so the tier's settings fail the collection by name
    result = subprocess.run(
        [
            SQ_EXECUTABLE,
            "run",
            str(answering_pipeline_path()),
            "--validate",
            "-p",
            f"{ANSWER_MODEL_PARAM}=validate-only",
            "-p",
            f"{CHECK_MODEL_PARAM}=validate-only",
        ],
        capture_output=True,
        text=True,
        timeout=VALIDATE_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "is valid" in result.stdout
