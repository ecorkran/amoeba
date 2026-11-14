"""``project_names`` against the real ``cf list projects --json`` recording."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.projects import (
    ProjectDetail,
    project_details,
    project_names,
)

RECORDING = (
    Path(__file__).parents[2] / "fixtures" / "context_forge" / "list_projects.json"
)


class _Runner:
    """A ``cf`` runner that prints fixed output and records its argv."""

    def __init__(self, stdout: str, *, returncode: int = 0, stderr: str = "") -> None:
        self.calls: list[Sequence[str]] = []
        self._result = (stdout, returncode, stderr)

    def __call__(
        self, argv: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        stdout, returncode, stderr = self._result
        return subprocess.CompletedProcess(list(argv), returncode, stdout, stderr)


def test_the_real_recording_parses_to_the_id_to_name_map() -> None:
    text = RECORDING.read_text(encoding="utf-8")
    expected = {entry["id"]: entry["name"] for entry in json.loads(text)}
    runner = _Runner(text)

    names = project_names(runner)

    assert names == expected
    assert isinstance(names, dict)
    assert names["project_1758069879482_xankquaj6"] == "trading"
    assert runner.calls == [["cf", "list", "projects", "--json"]]


def test_details_carry_the_path_or_none_from_the_real_recording() -> None:
    text = RECORDING.read_text(encoding="utf-8")
    entries = json.loads(text)
    runner = _Runner(text)

    details = project_details(runner)

    assert isinstance(details, dict)
    assert len(details) == len(entries)
    assert runner.calls == [["cf", "list", "projects", "--json"]]
    for entry in entries:
        assert details[entry["id"]] == ProjectDetail(
            entry["id"], entry["name"], entry.get("projectPath")
        )
    assert any(detail.path is None for detail in details.values())
    assert any(detail.path is not None for detail in details.values())


def test_details_fail_like_names_on_a_malformed_entry() -> None:
    result = project_details(_Runner('[{"id": "x"}]'))

    assert isinstance(result, CfCallFailed)


def test_the_recording_holds_an_entry_without_a_project_path() -> None:
    entries = json.loads(RECORDING.read_text(encoding="utf-8"))

    assert any("projectPath" not in entry for entry in entries)


@pytest.mark.parametrize(
    "stdout",
    [
        "not json",
        '{"id": "x", "name": "y"}',
        '[{"name": "no id"}]',
        '[{"id": "no name"}]',
        '[{"id": 7, "name": "numeric id"}]',
        "[42]",
    ],
)
def test_output_that_is_not_a_list_of_id_and_name_is_a_call_failure(
    stdout: str,
) -> None:
    result = project_names(_Runner(stdout))

    assert isinstance(result, CfCallFailed)
    assert "cf list projects --json" in result.detail


def test_a_nonzero_exit_is_a_call_failure_quoting_the_output() -> None:
    result = project_names(_Runner("", returncode=1, stderr="cf is broken"))

    assert isinstance(result, CfCallFailed)
    assert "exited 1" in result.detail
    assert "cf is broken" in result.detail


def test_a_cf_that_cannot_run_is_a_call_failure() -> None:
    def missing(argv: Sequence[str], **_kwargs: object) -> None:
        raise FileNotFoundError(argv[0])

    result = project_names(missing)  # pyright: ignore[reportArgumentType]

    assert isinstance(result, CfCallFailed)
