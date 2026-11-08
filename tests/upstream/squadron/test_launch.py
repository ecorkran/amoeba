"""The argv and the detached spawn of ``sq run``."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from sq_stub import RUN_SECONDS_ENV, write_sq_stub

from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.launch import (
    LaunchError,
    LaunchLogs,
    build_argv,
    spawn,
    stderr_confirms,
)

RUN_ID = "amoeba-20261023T101500Z-0123456789ab"
CHECKOUT = "/work/tree"


class FakeChild:
    def poll(self) -> int | None:
        return None


class FakePopen:
    """Records the call; optionally raises."""

    def __init__(self, error: OSError | None = None) -> None:
        self.error = error
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> FakeChild:
        self.calls.append((argv, kwargs))
        if self.error is not None:
            raise self.error
        return FakeChild()


@pytest.fixture
def logs(tmp_path: Path) -> LaunchLogs:
    directory = tmp_path / "logs"
    directory.mkdir()
    return LaunchLogs(directory / "run.stdout.log", directory / "run.stderr.log")


def test_the_argv_has_one_p_flag_per_param() -> None:
    argv = build_argv("noop", RUN_ID, {"a": "1", "b": "two words"})

    assert argv == [
        "sq", "run", "noop", "--run-id", RUN_ID, "-p", "a=1", "-p", "b=two words",
    ]  # fmt: skip


def test_the_slice_param_is_the_positional_target_and_the_rest_are_p_flags() -> None:
    """Squadron rejects `-p slice=131` and takes `sq run P4 131` (observed 0.23.7)."""
    argv = build_argv("P6", RUN_ID, {"slice": "131", "merge": "false"})

    assert argv == [
        "sq", "run", "P6", "131", "--run-id", RUN_ID, "-p", "merge=false",
    ]  # fmt: skip
    assert "slice=131" not in argv


@pytest.mark.parametrize("target", ["", "-x"], ids=["empty", "option"])
def test_a_target_that_is_not_a_usable_argument_is_rejected(target: str) -> None:
    with pytest.raises(ValueError, match="target"):
        build_argv("P4", RUN_ID, {"slice": target})


@pytest.mark.parametrize(
    "params", [{"a": "x,y"}, {"a,b": "1"}, {"a=b": "1"}], ids=["value", "comma", "eq"]
)
def test_params_squadron_would_split_are_rejected(params: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        build_argv("noop", RUN_ID, params)


def test_spawn_passes_the_detaching_arguments(logs: LaunchLogs) -> None:
    popen = FakePopen()
    argv = build_argv("noop", RUN_ID, {"slice": "122", "mode": "fast"})

    child = spawn(argv, CHECKOUT, logs, popen)

    assert isinstance(child, FakeChild)
    [(called_argv, kwargs)] = popen.calls
    assert called_argv == argv
    assert kwargs["cwd"] == CHECKOUT
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    assert kwargs["close_fds"] is True
    assert "env" not in kwargs, "the environment is inherited, not passed"
    assert kwargs["stdout"].name == str(logs.stdout)
    assert kwargs["stderr"].name == str(logs.stderr)
    assert kwargs["stdout"].closed and kwargs["stderr"].closed


def test_a_popen_oserror_is_a_spawn_error(logs: LaunchLogs) -> None:
    popen = FakePopen(FileNotFoundError("sq"))

    answer = spawn(["sq"], CHECKOUT, logs, popen)

    assert isinstance(answer, LaunchError)
    assert answer.failure is LaunchFailure.SPAWN_ERROR
    assert "FileNotFoundError" in answer.detail


def test_a_missing_log_directory_is_a_spawn_error_and_spawns_nothing(
    tmp_path: Path,
) -> None:
    popen = FakePopen()
    missing = tmp_path / "no-such-directory"
    gone = LaunchLogs(missing / "run.stdout.log", missing / "run.stderr.log")

    answer = spawn(["sq"], CHECKOUT, gone, popen)

    assert isinstance(answer, LaunchError)
    assert answer.failure is LaunchFailure.SPAWN_ERROR
    assert popen.calls == []


def test_an_existing_log_is_a_spawn_error_and_is_left_alone(
    logs: LaunchLogs,
) -> None:
    logs.stderr.write_text("earlier attempt")
    popen = FakePopen()

    answer = spawn(["sq"], CHECKOUT, logs, popen)

    assert isinstance(answer, LaunchError)
    assert "FileExistsError" in answer.detail
    assert popen.calls == []
    assert logs.stderr.read_text() == "earlier attempt"
    assert not logs.stdout.exists() or logs.stdout.stat().st_size == 0


def test_spawning_the_stub_sq_for_real(
    tmp_path: Path, logs: LaunchLogs, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    checkout = tmp_path / "checkout"
    home.mkdir()
    checkout.mkdir()
    bin_dir = write_sq_stub(tmp_path / "bin")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv(RUN_SECONDS_ENV, "0")

    child = spawn(
        build_argv("noop", RUN_ID, {"slice": "122"}),
        str(checkout),
        logs,
        subprocess.Popen,
    )
    assert not isinstance(child, LaunchError), child
    deadline = time.monotonic() + 20
    while child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)

    assert child.poll() is not None, "the child never exited"
    assert stderr_confirms(logs.stderr, RUN_ID)
