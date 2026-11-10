"""The run file reader against the real recorded file (slice 223, 2.4)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from amoeba.upstream.squadron.run_file import (
    ExecutionMode,
    RunFacts,
    RunFileProblem,
    read_run_facts,
)

REAL_FILE = (
    Path(__file__).parents[1] / "fixtures" / "squadron" / "run_file_schema5.json"
)
RUN_ID = "amoeba-fixture-pause-3"


def _runs_dir_with(tmp_path: Path, changes: dict[str, object | None]) -> Path:
    """The real run file with ``changes`` applied (``None`` removes the field)."""
    document = json.loads(REAL_FILE.read_text(encoding="utf-8"))
    for key, value in changes.items():
        if value is None:
            del document[key]
        else:
            document[key] = value
    (tmp_path / f"{RUN_ID}.json").write_text(json.dumps(document), encoding="utf-8")
    return tmp_path


def test_the_real_file_parses_with_its_params_and_mode(tmp_path: Path) -> None:
    shutil.copy(REAL_FILE, tmp_path / f"{RUN_ID}.json")

    facts = read_run_facts(tmp_path, RUN_ID)

    assert facts == RunFacts(
        params={"model": "haiku-xhigh"}, execution_mode=ExecutionMode.SDK
    )


def test_a_prompt_only_run_reads_as_prompt_only(tmp_path: Path) -> None:
    runs_dir = _runs_dir_with(tmp_path, {"execution_mode": "prompt-only"})

    facts = read_run_facts(runs_dir, RUN_ID)

    assert isinstance(facts, RunFacts)
    assert facts.execution_mode is ExecutionMode.PROMPT_ONLY


def test_a_missing_file_is_a_problem_naming_the_file(tmp_path: Path) -> None:
    problem = read_run_facts(tmp_path, RUN_ID)

    assert isinstance(problem, RunFileProblem)
    assert f"{RUN_ID}.json" in problem.reason


def test_an_unreadable_path_is_a_problem(tmp_path: Path) -> None:
    (tmp_path / f"{RUN_ID}.json").mkdir()

    assert isinstance(read_run_facts(tmp_path, RUN_ID), RunFileProblem)


def test_bad_json_is_a_problem(tmp_path: Path) -> None:
    (tmp_path / f"{RUN_ID}.json").write_text("{not json", encoding="utf-8")

    problem = read_run_facts(tmp_path, RUN_ID)

    assert isinstance(problem, RunFileProblem)
    assert "JSON" in problem.reason


def test_a_non_object_document_is_a_problem(tmp_path: Path) -> None:
    (tmp_path / f"{RUN_ID}.json").write_text("[1]", encoding="utf-8")

    assert isinstance(read_run_facts(tmp_path, RUN_ID), RunFileProblem)


@pytest.mark.parametrize("version", [4, 6, "5", None])
def test_another_schema_version_is_a_problem(
    tmp_path: Path, version: object | None
) -> None:
    runs_dir = _runs_dir_with(tmp_path, {"schema_version": version})

    problem = read_run_facts(runs_dir, RUN_ID)

    assert isinstance(problem, RunFileProblem)
    assert "schema_version" in problem.reason


@pytest.mark.parametrize("field", ["params", "execution_mode"])
def test_a_missing_field_is_a_problem_naming_it(tmp_path: Path, field: str) -> None:
    runs_dir = _runs_dir_with(tmp_path, {field: None})

    problem = read_run_facts(runs_dir, RUN_ID)

    assert isinstance(problem, RunFileProblem)
    assert field in problem.reason


def test_an_unknown_mode_is_a_problem_and_never_sdk(tmp_path: Path) -> None:
    runs_dir = _runs_dir_with(tmp_path, {"execution_mode": "hybrid"})

    problem = read_run_facts(runs_dir, RUN_ID)

    assert isinstance(problem, RunFileProblem)
    assert "hybrid" in problem.reason


def test_non_string_params_are_a_problem(tmp_path: Path) -> None:
    runs_dir = _runs_dir_with(tmp_path, {"params": {"slice": 5}})

    problem = read_run_facts(runs_dir, RUN_ID)

    assert isinstance(problem, RunFileProblem)
    assert "slice" in problem.reason
