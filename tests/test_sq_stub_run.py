"""The stub ``sq run`` mode: a detached launch that writes per-id state."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from sq_stub import (
    LOG_ENV,
    RUN_LATE_SECONDS_ENV,
    RUN_MODE_ENV,
    RUN_OUTCOME_ENV,
    RUN_SECONDS_ENV,
    STUB_STATE_RELATIVE,
    RunMode,
    write_sq_stub,
)

RUN_ID = "amoeba-20261023T101500Z-0123456789ab"


class Rig:
    """A stub ``sq`` under a temporary ``HOME``."""

    def __init__(self, tmp_path: Path) -> None:
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.log = tmp_path / "calls.log"
        self.stub = write_sq_stub(tmp_path / "bin") / "sq"

    def env(self, **extra: str) -> dict[str, str]:
        return {
            **os.environ,
            "HOME": str(self.home),
            LOG_ENV: str(self.log),
            RUN_SECONDS_ENV: "0",
            **extra,
        }

    def start(self, *arguments: str, **extra: str) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [sys.executable, str(self.stub), *arguments],
            env=self.env(**extra),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def run(self, *arguments: str, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.stub), *arguments],
            env=self.env(**extra),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def state(self, run_id: str = RUN_ID) -> dict[str, str] | None:
        path = self.home / STUB_STATE_RELATIVE / f"{run_id}.json"
        return json.loads(path.read_text()) if path.exists() else None


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def _launch(*extra: str) -> list[str]:
    return ["run", "noop", "--run-id", RUN_ID, "-p", "a=1", "-p", "b=2", *extra]


def test_a_normal_run_is_running_once_the_line_is_printed(rig: Rig) -> None:
    child = rig.start(*_launch(), **{RUN_SECONDS_ENV: "30"})
    assert child.stderr is not None
    assert child.stderr.readline() == f"run_id={RUN_ID}\n"
    assert rig.state() == {
        "run_id": RUN_ID,
        "outcome": "timed_out",
        "status": "timed_out",
    }
    child.kill()
    child.communicate()


def test_a_normal_run_ends_completed_and_exits_zero(rig: Rig) -> None:
    result = rig.run(*_launch())

    assert result.returncode == 0
    assert result.stderr == f"run_id={RUN_ID}\n"
    assert rig.state() == {
        "run_id": RUN_ID,
        "outcome": "completed",
        "status": "completed",
    }


def test_the_final_outcome_follows_the_environment(rig: Rig) -> None:
    result = rig.run(*_launch(), **{RUN_OUTCOME_ENV: "failed"})

    assert result.returncode == 0
    assert rig.state() == {"run_id": RUN_ID, "outcome": "failed", "status": "failed"}


def test_the_stub_waits_for_run_seconds_before_the_final_document(rig: Rig) -> None:
    started = time.monotonic()
    result = rig.run(*_launch(), **{RUN_SECONDS_ENV: "0.4"})

    assert result.returncode == 0
    assert time.monotonic() - started >= 0.4


def test_a_duplicate_id_exits_one_and_changes_nothing(rig: Rig) -> None:
    assert rig.run(*_launch(), **{RUN_OUTCOME_ENV: "failed"}).returncode == 0

    second = rig.run(*_launch())

    assert second.returncode == 1
    assert f"run_id={RUN_ID}" not in second.stderr
    assert rig.state() == {"run_id": RUN_ID, "outcome": "failed", "status": "failed"}


def test_an_unknown_flag_exits_two_without_state(rig: Rig) -> None:
    result = rig.run(*_launch("--bogus"))

    assert result.returncode == 2
    assert rig.state() is None


def test_a_malformed_id_exits_two_without_state(rig: Rig) -> None:
    result = rig.run("run", "noop", "--run-id", "-bad id", "-p", "a=1")

    assert result.returncode == 2
    assert not (rig.home / STUB_STATE_RELATIVE).exists()


def test_exit_before_line_exits_one_with_no_line_and_no_state(rig: Rig) -> None:
    result = rig.run(*_launch(), **{RUN_MODE_ENV: RunMode.EXIT_BEFORE_LINE.value})

    assert result.returncode == 1
    assert "run_id=" not in result.stderr
    assert rig.state() is None


def test_no_line_creates_the_state_but_never_prints_the_line(rig: Rig) -> None:
    result = rig.run(*_launch(), **{RUN_MODE_ENV: RunMode.NO_LINE.value})

    assert result.returncode == 0
    assert "run_id=" not in result.stderr
    assert rig.state() == {
        "run_id": RUN_ID,
        "outcome": "completed",
        "status": "completed",
    }


def test_late_line_creates_the_state_and_line_only_after_the_wait(rig: Rig) -> None:
    child = rig.start(
        *_launch(),
        **{
            RUN_MODE_ENV: RunMode.LATE_LINE.value,
            RUN_LATE_SECONDS_ENV: "1.0",
            RUN_SECONDS_ENV: "30",
        },
    )
    try:
        time.sleep(0.3)
        assert rig.state() is None
        assert child.stderr is not None
        assert child.stderr.readline() == f"run_id={RUN_ID}\n"
        assert rig.state() is not None
    finally:
        child.kill()
        child.communicate()


def test_usage_error_mode_exits_two_with_no_state(rig: Rig) -> None:
    result = rig.run(*_launch(), **{RUN_MODE_ENV: RunMode.USAGE_ERROR.value})

    assert result.returncode == 2
    assert rig.state() is None


def test_every_invocation_is_logged(rig: Rig) -> None:
    rig.run(*_launch())
    rig.run(*_launch())

    lines = rig.log.read_text().splitlines()
    assert lines == [" ".join(_launch())] * 2


def test_runs_wait_reads_what_run_wrote(rig: Rig) -> None:
    rig.run(*_launch())

    waited = rig.run("runs", "wait", RUN_ID, "--timeout", "0", "--json")

    assert waited.returncode == 0
    assert json.loads(waited.stdout)["outcome"] == "completed"
