"""The CI gate for the load bounds is the ``Tests`` step (slice 261, 15.4).

The load tier (``tests/load``) asserts latency and throughput bounds, and the guide
requires CI to gate them. The gate is the ``Tests`` step of
``.github/workflows/ci.yml``, a bare ``uv run pytest`` over everything ``addopts`` in
``pyproject.toml`` does not ignore, and only ``tests/live`` is ignored. This test parses
both files and fails if that step names paths or markers that leave ``tests/load`` out,
or if ``addopts`` ignores or deselects it.
"""

from __future__ import annotations

import shlex
import tomllib
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final = Path(__file__).parents[1]
WORKFLOW: Final = ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT: Final = ROOT / "pyproject.toml"
STEP_NAME: Final = "Tests"
LOAD_DIRECTORY: Final = "tests/load"
#: ``pytest`` options that take a value and narrow what is collected.
NARROWING_VALUE_OPTIONS: Final = {"-m", "-k", "--ignore", "--deselect", "--ignore-glob"}


def _tests_step_command() -> list[str]:
    workflow: dict[str, Any] = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == STEP_NAME:
                return shlex.split(str(step["run"]))
    raise AssertionError(f"ci.yml has no step named {STEP_NAME!r}")


def _addopts() -> list[str]:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    options: list[str] = config["tool"]["pytest"]["ini_options"]["addopts"]
    return options


def _narrowing(arguments: list[str]) -> list[str]:
    """The arguments that name a path, a marker or a keyword, or ignore or deselect."""
    found: list[str] = []
    for position, argument in enumerate(arguments):
        bare = argument.split("=", 1)[0]
        if bare in NARROWING_VALUE_OPTIONS:
            found.append(argument)
        elif not argument.startswith("-"):
            previous = arguments[position - 1] if position else ""
            if previous not in NARROWING_VALUE_OPTIONS:
                found.append(argument)
    return found


def test_the_tests_step_is_a_bare_pytest_that_names_no_path_or_marker() -> None:
    command = _tests_step_command()

    assert command[:3] == ["uv", "run", "pytest"]
    assert _narrowing(command[3:]) == [], "the Tests step must run everything"


def test_addopts_ignores_only_the_live_tier_and_never_the_load_tier() -> None:
    options = _addopts()

    assert [o for o in options if LOAD_DIRECTORY in o] == []
    assert not any(o.split("=", 1)[0] in {"-m", "-k", "--deselect"} for o in options)
    ignored = [o.split("=", 1)[1] for o in options if o.startswith("--ignore=")]
    assert ignored == ["tests/live"]


def test_the_load_tests_exist_where_a_bare_pytest_collects_them() -> None:
    assert list((ROOT / LOAD_DIRECTORY).glob("test_*.py"))
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert config["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


def test_the_gate_check_notices_a_step_that_leaves_the_load_tier_out() -> None:
    assert _narrowing(["tests/live"]) != []
    assert _narrowing(["-m", "not load"]) != []
    assert _narrowing(["--ignore=tests/load"]) != []
    assert _narrowing(["-q"]) == []
