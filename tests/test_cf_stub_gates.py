"""The stub ``cf``'s status fixtures and ``config get`` (slice 128, D1, D5)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from cf_stub import LOG_ENV, MODE_ENV, write_cf_stub
from cf_stub_gates import (
    CONFIG_ENV,
    CONFIG_MODE_ENV,
    STATUS_FIXTURE_ENV,
    STATUS_MAP_ENV,
    STATUS_MODE_ENV,
    GateMode,
    write_config_values,
    write_status_map,
)
from runner.gate_rig import (
    STATUS_FIXTURES,
    git_checkout,
    status_fixture,
    write_design,
    write_slice_list,
)

CONFIG_FIXTURES = Path(__file__).parent / "fixtures" / "cf" / "config"
LINK = "cf-1"


@pytest.fixture(autouse=True)
def stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = write_cf_stub(tmp_path / "bin")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    log = tmp_path / "cf.log"
    monkeypatch.setenv(LOG_ENV, str(log))
    for name in (
        MODE_ENV,
        STATUS_FIXTURE_ENV,
        STATUS_MAP_ENV,
        STATUS_MODE_ENV,
        CONFIG_ENV,
        CONFIG_MODE_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    return log


def _cf(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["cf", *arguments],
        capture_output=True,
        text=True,
        timeout=20.0,
        check=False,
        cwd=cwd,
    )


def _status(cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return _cf("status", "--json", "-p", LINK, cwd=cwd)


def _config(key: str) -> subprocess.CompletedProcess[str]:
    return _cf("config", "get", key, "--json", "-p", LINK)


@pytest.mark.parametrize(
    "name", sorted(path.stem for path in STATUS_FIXTURES.glob("*.json"))
)
def test_a_status_fixture_comes_back_byte_for_byte(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(STATUS_FIXTURE_ENV, str(STATUS_FIXTURES / f"{name}.json"))

    result = _status()

    assert result.returncode == 0
    assert result.stdout == (STATUS_FIXTURES / f"{name}.json").read_text("utf-8")


def test_with_no_fixture_status_gives_the_unchanged_probe_answer() -> None:
    result = _status()

    assert result.returncode == 0
    assert json.loads(result.stdout) == {"project": "stub"}


def test_each_checkout_answers_its_own_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv(
        STATUS_MAP_ENV,
        str(
            write_status_map(
                tmp_path / "map.json",
                {
                    first: STATUS_FIXTURES / "needs_tasks.json",
                    second: STATUS_FIXTURES / "complete.json",
                },
            )
        ),
    )

    assert json.loads(_status(first).stdout)["activeSlice"]["status"] == "needs-tasks"
    assert json.loads(_status(second).stdout)["activeSlice"]["status"] == "complete"
    assert json.loads(_status(tmp_path).stdout) == {"project": "stub"}


@pytest.mark.parametrize(
    ("name", "value"),
    [("integration_branch_set", "dev/erik"), ("integration_branch_empty", "")],
)
def test_config_get_answers_the_value_in_the_config_file(
    name: str, value: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = json.loads((CONFIG_FIXTURES / f"{name}.json").read_text("utf-8"))["key"]
    monkeypatch.setenv(
        CONFIG_ENV, str(write_config_values(tmp_path / "c.json", {key: value}))
    )

    document = json.loads(_config(key).stdout)

    assert document["key"] == key
    assert document["value"] == value


def test_a_config_key_nobody_set_answers_the_empty_string() -> None:
    document = json.loads(_config("git.integration_branch").stdout)

    assert document["value"] == ""
    assert document["source"] == "default"


def test_fail_mode_exits_one_for_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(STATUS_MODE_ENV, GateMode.FAIL.value)

    assert _status().returncode == 1


def test_fail_mode_exits_one_for_config_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_MODE_ENV, GateMode.FAIL.value)

    assert _config("git.integration_branch").returncode == 1


def test_not_json_mode_prints_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(STATUS_MODE_ENV, GateMode.NOT_JSON.value)

    assert _status().stdout.strip() == "this is not json"


def test_no_value_mode_leaves_the_value_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_MODE_ENV, GateMode.NO_VALUE.value)

    assert "value" not in json.loads(_config("git.integration_branch").stdout)


def test_every_gate_call_is_logged(stub: Path) -> None:
    _status()
    _config("git.integration_branch")

    assert stub.read_text().splitlines() == [
        f"status --json -p {LINK}",
        f"config get git.integration_branch --json -p {LINK}",
    ]


def test_the_plan_reads_still_work_beside_the_gate_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    knobs = write_slice_list(tmp_path / "plan", 120, {128: "slices/128-slice.x.md"})
    for name, value in knobs.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(MODE_ENV, raising=False)

    result = _cf("list", "slices", "120", "--json", "-p", LINK)

    entries = json.loads(result.stdout)["entries"]
    assert entries[0]["designFile"] == "slices/128-slice.x.md"


def test_the_rig_helpers_build_a_git_checkout_a_design_and_a_restated_fixture(
    tmp_path: Path,
) -> None:
    repo = git_checkout(tmp_path / "repo")
    design = write_design(repo, "slices/128-slice.x.md", {"review": "none"})
    restated = status_fixture(tmp_path / "s.json", "needs_tasks", 128)

    assert (repo / ".git").is_dir()
    assert "review: none" in design.read_text()
    assert json.loads(restated.read_text())["activeSlice"]["index"] == 128
