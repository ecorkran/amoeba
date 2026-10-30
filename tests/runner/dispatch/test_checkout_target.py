"""D5: the CF config reads run in the checkout and never default."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from amoeba.runner.budget import TickBudget
from amoeba.runner.dispatch.checkout_reads import (
    DEFAULT_TARGET_BRANCH,
    ReadFailure,
    read_config,
    read_target,
)
from amoeba.runner.lifecycle.plan_read import CF_KEY_INTEGRATION_BRANCH
from runner.observe_support import Clock, Host

FIXTURES = Path(__file__).parents[2] / "fixtures" / "cf"
CF_ID = "cf-1"
TIMEOUT = 8.0


class ScriptedCf:
    """A ``CfRun`` that answers once with a fixed process and records each call."""

    def __init__(
        self, stdout: str = "{}", returncode: int = 0, error: Exception | None = None
    ) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.error = error
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((argv, kwargs))
        if self.error is not None:
            raise self.error
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, "")


def _budget(deadline: float = 1_000.0) -> TickBudget:
    return TickBudget(deadline, Host(), Clock().monotonic)


def _fixture(kind: str, name: str) -> str:
    return (FIXTURES / kind / f"{name}.json").read_text()


@pytest.mark.parametrize(
    ("name", "key", "value"),
    [
        ("integration_branch_empty", CF_KEY_INTEGRATION_BRANCH, ""),
        ("integration_branch_set", CF_KEY_INTEGRATION_BRANCH, "dev/erik"),
    ],
)
def test_a_config_read_returns_the_captured_value(
    name: str, key: str, value: str, tmp_path: Path
) -> None:
    cf = ScriptedCf(_fixture("config", name))

    assert read_config(key, tmp_path, CF_ID, _budget(), cf, TIMEOUT) == value

    [(argv, kwargs)] = cf.calls
    assert argv == ["cf", "config", "get", key, "--json", "-p", CF_ID]
    assert kwargs["cwd"] == tmp_path


def test_an_empty_integration_branch_is_main(tmp_path: Path) -> None:
    cf = ScriptedCf(_fixture("config", "integration_branch_empty"))

    target = read_target(tmp_path, CF_ID, _budget(), cf, TIMEOUT)

    assert target == DEFAULT_TARGET_BRANCH == "main"


def test_a_set_integration_branch_is_the_target(tmp_path: Path) -> None:
    cf = ScriptedCf(_fixture("config", "integration_branch_set"))

    assert read_target(tmp_path, CF_ID, _budget(), cf, TIMEOUT) == "dev/erik"


@pytest.mark.parametrize(
    "stdout",
    ['{"key": "git.integration_branch"}', '{"value": null}', '{"value": 3}'],
    ids=["no value", "null value", "number value"],
)
def test_a_value_that_is_not_a_string_is_a_failure_never_a_default(
    stdout: str, tmp_path: Path
) -> None:
    cf = ScriptedCf(stdout)

    assert isinstance(read_target(tmp_path, CF_ID, _budget(), cf, TIMEOUT), ReadFailure)


def test_a_non_zero_exit_is_a_failure_naming_the_command(tmp_path: Path) -> None:
    cf = ScriptedCf("boom", returncode=1)

    result = read_target(tmp_path, CF_ID, _budget(), cf, TIMEOUT)

    assert isinstance(result, ReadFailure)
    assert "cf config get" in result.detail and "exited 1" in result.detail


@pytest.mark.parametrize("stdout", ["not json", "[1, 2]"], ids=["text", "array"])
def test_output_that_is_not_a_json_object_is_a_failure(
    stdout: str, tmp_path: Path
) -> None:
    result = read_target(tmp_path, CF_ID, _budget(), ScriptedCf(stdout), TIMEOUT)

    assert isinstance(result, ReadFailure)


@pytest.mark.parametrize(
    "error",
    [subprocess.TimeoutExpired("cf", TIMEOUT), FileNotFoundError("cf")],
)
def test_a_timeout_and_a_missing_cf_are_failures(
    error: Exception, tmp_path: Path
) -> None:
    result = read_target(tmp_path, CF_ID, _budget(), ScriptedCf(error=error), TIMEOUT)

    assert isinstance(result, ReadFailure)


def test_a_spent_budget_starts_nothing(tmp_path: Path) -> None:
    cf = ScriptedCf()
    spent = _budget(deadline=0.0)

    assert read_target(tmp_path, CF_ID, spent, cf, TIMEOUT) is None
    assert cf.calls == []
