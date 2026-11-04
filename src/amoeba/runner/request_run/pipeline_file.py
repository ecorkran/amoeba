"""Names of the shipped slice-writing pipeline, defined once (slice 180, D1 to D8).

The pipeline YAML, the request directory preparation, the reply reader, the probe
and the tests all import these names; a test asserts the YAML uses exactly them.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Final

PIPELINE_FILE_NAME: Final = "slice_writing.yaml"

WRITE_STEP: Final = "write"
COMMIT_STEP: Final = "commit"

REQUESTS_INDEX_PARAM: Final = "requests-index"
MODEL_PARAM: Final = "model"

# Input Amoeba writes into the run I/O directory.
NEED_FILE: Final = "need.md"

# Outputs Squadron writes into the run I/O directory.
REPLY_FILE: Final = "reply.json"
WRITE_PROMPT_FILE: Final = "write.prompt.md"

# The commit step's `paths` (D2): the only files a run may change. The slice-plan
# glob carries the requests index as a pipeline param placeholder.
INITIATIVE_PLAN_GLOB: Final = (
    "project-documents/user/project-guides/*-initiative-plan.*.md"
)
SLICE_PLAN_GLOB: Final = (
    "project-documents/user/architecture/{" + REQUESTS_INDEX_PARAM + "}-slices.*.md"
)
COMMIT_PATHS: Final = (INITIATIVE_PLAN_GLOB, SLICE_PLAN_GLOB)
COMMIT_MESSAGE: Final = "docs: add request slice to the requests initiative plan"

# `sq run` option names for the run I/O directory and the per-run cost cap. These
# are proposals until Task 9.1 confirms them against the shipped Squadron.
IO_DIRECTORY_OPTION: Final = "--io-dir"
MAX_COST_OPTION: Final = "--max-cost"

# The probe validates the options; it never spends, so the cap is nominal (USD).
PROBE_MAX_COST_USD: Final = 1


def slice_writing_pipeline_path() -> Path:
    """Absolute path of the shipped pipeline file.

    Raises:
        FileNotFoundError: When the file is not in the package.
    """
    resource = resources.files("amoeba.runner.request_run").joinpath(PIPELINE_FILE_NAME)
    path = Path(str(resource))
    if not path.is_file():
        raise FileNotFoundError(f"slice-writing pipeline file is missing: {path}")
    return path.resolve()
