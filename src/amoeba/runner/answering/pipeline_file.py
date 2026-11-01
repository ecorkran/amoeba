"""Names of the shipped answering pipeline, defined once (slice 140, D3 to D7).

The pipeline YAML, the scratch preparation, the reply parsers and the tests all
import these names; a test asserts the YAML uses exactly them.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Final

PIPELINE_FILE_NAME: Final = "answering.yaml"

ANSWER_STEP: Final = "answer"
CHECK_STEP: Final = "check"

ANSWER_MODEL_PARAM: Final = "answer-model"
CHECK_MODEL_PARAM: Final = "check-model"

# Inputs Amoeba writes into the scratch directory.
QUESTION_FILE: Final = "question.md"
PASSAGES_FILE: Final = "passages.md"
RULES_DIRECTORY: Final = "rules"
SQUADRON_CONFIG_FILE: Final = ".squadron.toml"

# Outputs Squadron writes into the scratch directory.
ANSWER_REPLY_FILE: Final = "answer.json"
ANSWER_PROMPT_FILE: Final = "answer.prompt.md"
CHECK_REPLY_FILE: Final = "check.json"
CHECK_PROMPT_FILE: Final = "check.prompt.md"


def answering_pipeline_path() -> Path:
    """Absolute path of the shipped pipeline file.

    Raises:
        FileNotFoundError: When the file is not in the package.
    """
    resource = resources.files("amoeba.runner.answering").joinpath(PIPELINE_FILE_NAME)
    path = Path(str(resource))
    if not path.is_file():
        raise FileNotFoundError(f"answering pipeline file is missing: {path}")
    return path.resolve()
