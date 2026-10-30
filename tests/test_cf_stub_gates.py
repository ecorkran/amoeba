"""The stub ``cf``'s ``config get`` (slice 128, D5)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from cf_stub import LOG_ENV, MODE_ENV, write_cf_stub
from cf_stub_gates import CONFIG_ENV, CONFIG_MODE_ENV, GateMode, write_config_values

CONFIG_FIXTURES = Path(__file__).parent / "fixtures" / "cf" / "config"
LINK = "cf-1"


@pytest.fixture(autouse=True)
def stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = write_cf_stub(tmp_path / "bin")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    log = tmp_path / "cf.log"
    monkeypatch.setenv(LOG_ENV, str(log))
    for name in (MODE_ENV, CONFIG_ENV, CONFIG_MODE_ENV):
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


def _config(key: str) -> subprocess.CompletedProcess[str]:
    return _cf("config", "get", key, "--json", "-p", LINK)


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


def test_fail_mode_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_MODE_ENV, GateMode.FAIL.value)

    assert _config("git.integration_branch").returncode == 1


def test_no_value_mode_leaves_the_value_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_MODE_ENV, GateMode.NO_VALUE.value)

    assert "value" not in json.loads(_config("git.integration_branch").stdout)


def test_every_config_call_is_logged(stub: Path) -> None:
    _config("git.integration_branch")

    assert stub.read_text().splitlines() == [
        f"config get git.integration_branch --json -p {LINK}"
    ]
