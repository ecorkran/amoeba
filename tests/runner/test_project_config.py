"""D8: the per-project config file, loaded once, every problem named."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.process import StartupFailedError
from amoeba.runner.project_config import (
    PROJECT_DEFAULTS,
    AnswererSettings,
    load_project_config,
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "projects.yaml"
    path.write_text(text)
    return path


def test_no_path_gives_every_project_the_defaults() -> None:
    config = load_project_config(None)

    assert config.for_project("anything") == PROJECT_DEFAULTS


def test_a_project_the_file_does_not_name_takes_the_defaults(tmp_path: Path) -> None:
    path = _write(tmp_path, "projects:\n  scratch:\n    pipeline: p456\n")

    assert load_project_config(path).for_project("other") == PROJECT_DEFAULTS


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


@pytest.mark.parametrize("key", ["merge_policy", "merge_polcy"])
def test_an_unknown_key_is_refused(tmp_path: Path, key: str) -> None:
    path = _write(
        tmp_path, f"projects:\n  scratch:\n    pipeline: p456\n    {key}: auto\n"
    )

    with pytest.raises(StartupFailedError, match=key):
        load_project_config(path)


def test_every_problem_in_one_file_is_named(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "projects:\n  a:\n    pipeline: p456\n    merge_policy: auto\n"
        "  b:\n    pipeline: p456\n    colour: red\n",
    )

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert "merge_policy" in str(raised.value)
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
        ("    params: {k: v}\n", "projects.a.pipeline"),
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
        "  b:\n    params: {k: v}\n",
    )

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert "projects.a.params.slice" in str(raised.value)
    assert "projects.b.pipeline" in str(raised.value)


# --------------------------------------------------------------------------
# The answerer section (slice 141, D6)
# --------------------------------------------------------------------------

# The real projects.yaml layout, as an operator writes it.
ANSWERER_FILE = """\
projects:
  scratch:
    pipeline: p456
    answerer:
      answer_limit: 3
      reserved_terms: [drop table, "  force push  "]
  plain:
    pipeline: p456
"""


def _answerer_file(answerer_body: str) -> str:
    return f"projects:\n  scratch:\n    pipeline: p456\n    answerer: {answerer_body}\n"


def test_a_configured_answerer_is_on_and_an_absent_key_is_not(
    tmp_path: Path,
) -> None:
    config = load_project_config(_write(tmp_path, ANSWERER_FILE))

    assert config.for_project("scratch").answerer == AnswererSettings(
        answer_limit=3, reserved_terms=["drop table", "force push"]
    )
    assert config.for_project("plain").answerer is None
    assert config.for_project("unnamed").answerer is None


def test_a_null_answerer_fails_naming_the_project_path(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "projects:\n  scratch:\n    pipeline: p456\n    answerer:\n"
    )

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert "projects.scratch.answerer" in str(raised.value)
    assert "answerer must be a mapping" in str(raised.value)


def test_an_unknown_key_inside_answerer_fails(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        _answerer_file("{answer_limit: 3, reserved_terms: [], limit: 3}"),
    )

    with pytest.raises(StartupFailedError) as raised:
        load_project_config(path)

    assert "projects.scratch.answerer.limit" in str(raised.value)


def test_an_empty_answerer_fails_naming_both_missing_keys(tmp_path: Path) -> None:
    with pytest.raises(StartupFailedError) as raised:
        load_project_config(_write(tmp_path, _answerer_file("{}")))

    assert "projects.scratch.answerer.answer_limit" in str(raised.value)
    assert "projects.scratch.answerer.reserved_terms" in str(raised.value)


@pytest.mark.parametrize(
    ("body", "failing_path"),
    [
        ("{reserved_terms: []}", "answerer.answer_limit"),
        ("{answer_limit: 2}", "answerer.reserved_terms"),
        ("{answer_limit: 0, reserved_terms: []}", "answerer.answer_limit"),
        ("{answer_limit: -1, reserved_terms: []}", "answerer.answer_limit"),
        ("{answer_limit: 1.5, reserved_terms: []}", "answerer.answer_limit"),
        ("{answer_limit: '2', reserved_terms: []}", "answerer.answer_limit"),
        ("{answer_limit: 2, reserved_terms: ['  ']}", "answerer.reserved_terms.0"),
        ("{answer_limit: 2, reserved_terms: ['ok', '']}", "answerer.reserved_terms.1"),
        ("{answer_limit: 2, reserved_terms: [7]}", "answerer.reserved_terms.0"),
        ("{answer_limit: 2, reserved_terms: drop}", "answerer.reserved_terms"),
    ],
)
def test_a_bad_answerer_value_fails_with_its_key_path(
    tmp_path: Path, body: str, failing_path: str
) -> None:
    with pytest.raises(StartupFailedError) as raised:
        load_project_config(_write(tmp_path, _answerer_file(body)))

    assert f"projects.scratch.{failing_path}" in str(raised.value)


def test_an_empty_reserved_terms_list_loads(tmp_path: Path) -> None:
    config = load_project_config(
        _write(tmp_path, _answerer_file("{answer_limit: 1, reserved_terms: []}"))
    )

    assert config.for_project("scratch").answerer == AnswererSettings(
        answer_limit=1, reserved_terms=[]
    )
