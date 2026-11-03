"""``answering.yaml`` uses exactly the names of ``pipeline_file.py`` (slice 140)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from amoeba.runner.answering import pipeline_file
from amoeba.runner.answering.artifacts import AnswerKind, Verdict
from amoeba.runner.answering.pipeline_file import (
    ANSWER_MODEL_PARAM,
    ANSWER_PROMPT_FILE,
    ANSWER_REPLY_FILE,
    ANSWER_STEP,
    CHECK_MODEL_PARAM,
    CHECK_PROMPT_FILE,
    CHECK_REPLY_FILE,
    CHECK_STEP,
    PASSAGES_FILE,
    PIPELINE_FILE_NAME,
    QUESTION_FILE,
    answering_pipeline_path,
)


def _load() -> dict[str, Any]:
    document: Any = yaml.safe_load(
        answering_pipeline_path().read_text(encoding="utf-8")
    )
    assert isinstance(document, dict)
    return cast("dict[str, Any]", document)


def _steps() -> dict[str, dict[str, Any]]:
    """Step name to its config; asserts each step is a one-key ``dispatch`` entry."""
    steps: dict[str, dict[str, Any]] = {}
    for entry in _load()["steps"]:
        assert list(entry) == ["dispatch"]
        steps[entry["dispatch"]["name"]] = entry["dispatch"]
    return steps


def test_step_names_and_order() -> None:
    assert list(_steps()) == [ANSWER_STEP, CHECK_STEP]


def test_params_are_required_with_no_default() -> None:
    assert _load()["params"] == {
        ANSWER_MODEL_PARAM: "required",
        CHECK_MODEL_PARAM: "required",
    }


def test_models_come_from_the_params() -> None:
    steps = _steps()
    assert steps[ANSWER_STEP]["model"] == "{" + ANSWER_MODEL_PARAM + "}"
    assert steps[CHECK_STEP]["model"] == "{" + CHECK_MODEL_PARAM + "}"


def test_reply_and_prompt_files() -> None:
    steps = _steps()
    assert steps[ANSWER_STEP]["reply_file"] == ANSWER_REPLY_FILE
    assert steps[ANSWER_STEP]["delivered_prompt_file"] == ANSWER_PROMPT_FILE
    assert steps[CHECK_STEP]["reply_file"] == CHECK_REPLY_FILE
    assert steps[CHECK_STEP]["delivered_prompt_file"] == CHECK_PROMPT_FILE


def test_prompt_files_and_reply_chaining() -> None:
    steps = _steps()
    both = [QUESTION_FILE, PASSAGES_FILE]
    assert steps[ANSWER_STEP]["prompt_files"] == both
    assert steps[CHECK_STEP]["prompt_files"] == both
    assert steps[CHECK_STEP]["reply_from"] == ANSWER_STEP
    assert "reply_from" not in steps[ANSWER_STEP]


def test_no_tools_and_json_reply() -> None:
    for step in _steps().values():
        assert step["allowed_tools"] == []
        assert step["reply_format"] == "json"


def test_prompts_name_the_parser_vocabulary() -> None:
    steps = _steps()
    answer_prompt = steps[ANSWER_STEP]["prompt"]
    check_prompt = steps[CHECK_STEP]["prompt"]
    assert answer_prompt.strip()
    assert check_prompt.strip()
    for kind in AnswerKind:
        assert f'"{kind.value}"' in answer_prompt
    for verdict in Verdict:
        assert f'"{verdict.value}"' in check_prompt
    assert '"verdict"' in check_prompt


def test_pipeline_name_matches_file_stem() -> None:
    assert _load()["name"] == Path(PIPELINE_FILE_NAME).stem


def test_path_resolves_to_an_existing_file() -> None:
    path = answering_pipeline_path()
    assert path.is_absolute()
    assert path.is_file()
    assert path.name == PIPELINE_FILE_NAME


def test_missing_file_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    def package_root(_package: str) -> Path:
        return tmp_path

    monkeypatch.setattr(pipeline_file.resources, "files", package_root)
    with pytest.raises(FileNotFoundError, match=PIPELINE_FILE_NAME):
        answering_pipeline_path()
