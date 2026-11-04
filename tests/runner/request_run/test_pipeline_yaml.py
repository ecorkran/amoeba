"""``slice_writing.yaml`` uses exactly the names of ``pipeline_file.py`` (slice 180)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from amoeba.runner.request_run import pipeline_file
from amoeba.runner.request_run.pipeline_file import (
    COMMIT_MESSAGE,
    COMMIT_PATHS,
    COMMIT_STEP,
    INITIATIVE_PLAN_GLOB,
    MODEL_PARAM,
    NEED_FILE,
    PIPELINE_FILE_NAME,
    REPLY_FILE,
    REQUESTS_INDEX_PARAM,
    SLICE_PLAN_GLOB,
    WRITE_PROMPT_FILE,
    WRITE_STEP,
    slice_writing_pipeline_path,
)

_BARE_BRACES = re.compile(r"\{([^\s\"'{}]+)\}")
_HEX_RUN = re.compile(r"\b[0-9a-fA-F]{7,40}\b")


def _load() -> dict[str, Any]:
    document: Any = yaml.safe_load(
        slice_writing_pipeline_path().read_text(encoding="utf-8")
    )
    assert isinstance(document, dict)
    return cast("dict[str, Any]", document)


def _steps() -> list[tuple[str, dict[str, Any]]]:
    """Each step as (step type, config); asserts one-key entries."""
    steps: list[tuple[str, dict[str, Any]]] = []
    for entry in _load()["steps"]:
        assert len(entry) == 1
        ((step_type, config),) = entry.items()
        steps.append((step_type, config))
    return steps


def _write_step() -> dict[str, Any]:
    return _steps()[0][1]


def _all_keys(node: object) -> set[str]:
    if isinstance(node, dict):
        mapping = cast("dict[str, object]", node)
        return set(mapping) | {k for v in mapping.values() for k in _all_keys(v)}
    if isinstance(node, list):
        return {k for item in cast("list[object]", node) for k in _all_keys(item)}
    return set()


def test_step_names_and_order() -> None:
    steps = _steps()
    assert [(kind, config["name"]) for kind, config in steps] == [
        ("dispatch", WRITE_STEP),
        ("commit", COMMIT_STEP),
    ]


def test_params_are_required_with_no_default_and_ordered() -> None:
    params = _load()["params"]
    assert params == {REQUESTS_INDEX_PARAM: "required", MODEL_PARAM: "required"}
    # The first required param is the positional target of `sq run`.
    assert list(params) == [REQUESTS_INDEX_PARAM, MODEL_PARAM]


def test_write_step_files_and_model() -> None:
    step = _write_step()
    assert step["model"] == "{" + MODEL_PARAM + "}"
    assert step["prompt_files"] == [NEED_FILE]
    assert step["reply_file"] == REPLY_FILE
    assert step["delivered_prompt_file"] == WRITE_PROMPT_FILE
    assert step["reply_format"] == "json"


def test_write_step_declares_no_tool_restriction() -> None:
    assert "allowed_tools" not in _write_step()


def test_commit_step_paths_and_message() -> None:
    commit = _steps()[1][1]
    assert tuple(commit["paths"]) == COMMIT_PATHS
    assert commit["message"] == COMMIT_MESSAGE


def test_no_cost_cap_or_timeout_in_the_file() -> None:
    keys = _all_keys(_load())
    assert not [k for k in keys if "max_cost" in k or "timeout" in k]


def test_prompt_braces_are_only_real_params() -> None:
    prompt = _write_step()["prompt"]
    assert prompt.strip()
    found = set(_BARE_BRACES.findall(prompt))
    assert found <= {REQUESTS_INDEX_PARAM, MODEL_PARAM}


def test_prompt_has_no_literal_hash() -> None:
    assert _HEX_RUN.findall(_write_step()["prompt"]) == []


def test_prompt_names_both_globs() -> None:
    prompt = _write_step()["prompt"]
    assert INITIATIVE_PLAN_GLOB in prompt
    assert SLICE_PLAN_GLOB in prompt


def test_prompt_states_the_reply_shapes() -> None:
    prompt = _write_step()["prompt"]
    assert '"kind": "new_slice"' in prompt
    assert '"kind": "already_met"' in prompt


def test_pipeline_name_matches_file_stem() -> None:
    assert _load()["name"] == "slice-writing"
    assert Path(PIPELINE_FILE_NAME).stem.replace("_", "-") == _load()["name"]


def test_path_resolves_to_an_existing_file() -> None:
    path = slice_writing_pipeline_path()
    assert path.is_absolute()
    assert path.is_file()
    assert path.as_posix().endswith("amoeba/runner/request_run/slice_writing.yaml")


def test_missing_file_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    def package_root(_package: str) -> Path:
        return tmp_path

    monkeypatch.setattr(pipeline_file.resources, "files", package_root)
    with pytest.raises(FileNotFoundError, match=PIPELINE_FILE_NAME):
        slice_writing_pipeline_path()
