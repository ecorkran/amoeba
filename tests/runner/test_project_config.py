"""D8: the per-project config file, loaded once, every problem named."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.process import StartupFailedError
from amoeba.runner.project_config import (
    PROJECT_DEFAULTS,
    MergePolicy,
    load_project_config,
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "projects.yaml"
    path.write_text(text)
    return path


def test_no_path_gives_every_project_the_defaults() -> None:
    config = load_project_config(None)

    assert config.for_project("anything") == PROJECT_DEFAULTS
    assert PROJECT_DEFAULTS.merge_policy is MergePolicy.AUTO


def test_a_named_project_takes_its_own_policy(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "projects:\n"
        "  amoeba:\n    merge_policy: human\n"
        "  scratch:\n    merge_policy: auto\n",
    )

    config = load_project_config(path)

    assert config.for_project("scratch").merge_policy is MergePolicy.AUTO
    assert config.for_project("amoeba").merge_policy is MergePolicy.HUMAN


def test_a_project_the_file_does_not_name_takes_the_defaults(tmp_path: Path) -> None:
    path = _write(tmp_path, "projects:\n  scratch:\n    merge_policy: auto\n")

    assert load_project_config(path).for_project("other") == PROJECT_DEFAULTS


def test_a_key_a_project_entry_omits_takes_the_default(tmp_path: Path) -> None:
    path = _write(tmp_path, "projects:\n  scratch: {}\n")

    assert load_project_config(path).for_project("scratch") == PROJECT_DEFAULTS


def test_a_value_is_trimmed_and_lower_cased(tmp_path: Path) -> None:
    path = _write(tmp_path, 'projects:\n  scratch:\n    merge_policy: " Auto "\n')

    assert load_project_config(path).for_project("scratch").merge_policy is (
        MergePolicy.AUTO
    )


def test_a_missing_file_is_a_startup_failure_naming_the_path(tmp_path: Path) -> None:
    path = tmp_path / "absent.yaml"

    with pytest.raises(StartupFailedError, match="absent.yaml"):
        load_project_config(path)


def test_a_file_that_is_not_yaml_is_a_startup_failure(tmp_path: Path) -> None:
    with pytest.raises(StartupFailedError, match="not valid YAML"):
        load_project_config(_write(tmp_path, "projects: [unclosed\n"))


def test_a_file_that_is_not_a_mapping_is_a_startup_failure(tmp_path: Path) -> None:
    with pytest.raises(StartupFailedError, match="mapping"):
        load_project_config(_write(tmp_path, "- just\n- a list\n"))


def test_an_unknown_value_names_the_key_and_the_value(tmp_path: Path) -> None:
    path = _write(tmp_path, "projects:\n  scratch:\n    merge_policy: sometimes\n")

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert "merge_policy" in str(raised.value)
    assert "sometimes" in str(raised.value)


def test_an_unknown_key_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "projects:\n  scratch:\n    merge_polcy: auto\n")

    with pytest.raises(StartupFailedError, match="merge_polcy"):
        load_project_config(path)


def test_every_problem_in_one_file_is_named(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "projects:\n  a:\n    merge_policy: sometimes\n  b:\n    colour: red\n",
    )

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert "sometimes" in str(raised.value)
    assert "colour" in str(raised.value)
