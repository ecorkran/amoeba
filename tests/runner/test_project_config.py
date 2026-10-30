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
        "  amoeba:\n    pipeline: p456\n    merge_policy: human\n"
        "  scratch:\n    pipeline: p456\n    merge_policy: auto\n",
    )

    config = load_project_config(path)

    assert config.for_project("scratch").merge_policy is MergePolicy.AUTO
    assert config.for_project("amoeba").merge_policy is MergePolicy.HUMAN


def test_a_project_the_file_does_not_name_takes_the_defaults(tmp_path: Path) -> None:
    path = _write(tmp_path, "projects:\n  scratch:\n    pipeline: p456\n")

    assert load_project_config(path).for_project("other") == PROJECT_DEFAULTS


def test_a_key_a_project_entry_omits_takes_the_default(tmp_path: Path) -> None:
    path = _write(tmp_path, "projects:\n  scratch:\n    pipeline: p456\n")

    settings = load_project_config(path).for_project("scratch")

    assert settings.merge_policy is PROJECT_DEFAULTS.merge_policy


def test_a_value_is_trimmed_and_lower_cased(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'projects:\n  scratch:\n    pipeline: p456\n    merge_policy: " Auto "\n',
    )

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
    path = _write(
        tmp_path,
        "projects:\n  scratch:\n    pipeline: p456\n    merge_policy: sometimes\n",
    )

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert "merge_policy" in str(raised.value)
    assert "sometimes" in str(raised.value)


def test_an_unknown_key_is_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "projects:\n  scratch:\n    pipeline: p456\n    merge_polcy: auto\n"
    )

    with pytest.raises(StartupFailedError, match="merge_polcy"):
        load_project_config(path)


def test_every_problem_in_one_file_is_named(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "projects:\n  a:\n    pipeline: p456\n    merge_policy: sometimes\n"
        "  b:\n    pipeline: p456\n    colour: red\n",
    )

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert "sometimes" in str(raised.value)
    assert "colour" in str(raised.value)


def test_a_named_project_carries_its_pipeline_and_params(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "projects:\n  a:\n    pipeline: p456\n    params:\n      model: opus\n"
        "  b:\n    pipeline: p4567\n",
    )

    config = load_project_config(path)

    assert config.for_project("a").pipeline == "p456"
    assert config.for_project("a").params == {"model": "opus"}
    assert config.for_project("b").pipeline == "p4567"
    assert config.for_project("b").params == {}


def test_a_project_the_file_does_not_name_has_no_pipeline(tmp_path: Path) -> None:
    path = _write(tmp_path, "projects:\n  a:\n    pipeline: p456\n")

    assert load_project_config(path).for_project("other").pipeline is None
    assert load_project_config(None).for_project("other").pipeline is None


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("    merge_policy: auto\n", "projects.a.pipeline"),
        ("    pipeline: ''\n", "projects.a.pipeline"),
        ("    pipeline: p456\n    params: {slice: '1'}\n", "projects.a.params.slice"),
        ("    pipeline: p456\n    params: {'a,b': x}\n", "projects.a.params.a,b"),
        ("    pipeline: p456\n    params: {'a=b': x}\n", "projects.a.params.a=b"),
        ("    pipeline: p456\n    params: {k: 'x,y'}\n", "projects.a.params.k"),
        ("    pipeline: p456\n    params: {k: 3}\n", "projects.a.params.k"),
        ("    pipeline: p456\n    mode: fast\n", "mode"),
    ],
)
def test_each_pipeline_or_params_failure_is_named(
    tmp_path: Path, entry: str, expected: str
) -> None:
    path = _write(tmp_path, "projects:\n  a:\n" + entry)

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert expected in str(raised.value)


def test_two_params_problems_in_one_file_are_both_named(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "projects:\n  a:\n    pipeline: p456\n    params: {slice: '1'}\n"
        "  b:\n    merge_policy: auto\n",
    )

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert "projects.a.params.slice" in str(raised.value)
    assert "projects.b.pipeline" in str(raised.value)
