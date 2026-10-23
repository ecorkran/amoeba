"""The detached launch and the tracker of launched children."""

from __future__ import annotations

import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sq_stub import RUN_SECONDS_ENV, write_sq_stub

from amoeba.runner.faults import LaunchFailure
from amoeba.runner.launch import (
    LAUNCH_LOGS_DIRNAME,
    PARAM_PARAMS,
    PARAM_PIPELINE,
    LaunchError,
    LaunchTracker,
    build_argv,
    launch,
    log_paths,
    stderr_confirms,
)
from amoeba.store import PARAM_CHECKOUT, PARAM_RUN_ID, CommandKind, JournalEntry

RUN_ID = "amoeba-20261023T101500Z-0123456789ab"
ENTRY_ID = "entry-1"


def _entry(
    params: dict[str, object] | None = None, checkout: str = "/work/tree"
) -> JournalEntry:
    return JournalEntry(
        id=ENTRY_ID,
        project_id="demo",
        node_id="node-1",
        kind=CommandKind.SQ_RUN,
        parameters={
            PARAM_PIPELINE: "noop",
            PARAM_PARAMS: {"slice": "122", "mode": "fast"}
            if params is None
            else params,
            PARAM_RUN_ID: RUN_ID,
            PARAM_CHECKOUT: checkout,
        },
        issued_at=datetime(2026, 10, 23, tzinfo=UTC),
    )


class FakeChild:
    def __init__(self, exit_code: int | None = None) -> None:
        self.exit_code = exit_code
        self.polls = 0

    def poll(self) -> int | None:
        self.polls += 1
        return self.exit_code


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
def supervisor_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "supervisor"
    (directory / LAUNCH_LOGS_DIRNAME).mkdir(parents=True)
    return directory


def test_the_argv_has_one_p_flag_per_param() -> None:
    argv = build_argv("noop", RUN_ID, {"a": "1", "b": "two words"})

    assert argv == [
        "sq", "run", "noop", "--run-id", RUN_ID, "-p", "a=1", "-p", "b=two words",
    ]  # fmt: skip


@pytest.mark.parametrize(
    "params", [{"a": "x,y"}, {"a,b": "1"}, {"a=b": "1"}], ids=["value", "comma", "eq"]
)
def test_params_squadron_would_split_are_rejected(params: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        build_argv("noop", RUN_ID, params)


def test_launch_passes_the_detaching_arguments(supervisor_dir: Path) -> None:
    popen = FakePopen()

    child = launch(_entry(), supervisor_dir, popen)

    assert isinstance(child, FakeChild)
    [(argv, kwargs)] = popen.calls
    assert argv == build_argv("noop", RUN_ID, {"slice": "122", "mode": "fast"})
    assert kwargs["cwd"] == "/work/tree"
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    assert kwargs["close_fds"] is True
    assert "env" not in kwargs, "the environment is inherited, not passed"
    logs = log_paths(supervisor_dir, ENTRY_ID)
    assert kwargs["stdout"].name == str(logs.stdout)
    assert kwargs["stderr"].name == str(logs.stderr)
    assert kwargs["stdout"].closed and kwargs["stderr"].closed


def test_a_popen_oserror_is_a_spawn_error(supervisor_dir: Path) -> None:
    popen = FakePopen(FileNotFoundError("sq"))

    answer = launch(_entry(), supervisor_dir, popen)

    assert isinstance(answer, LaunchError)
    assert answer.failure is LaunchFailure.SPAWN_ERROR
    assert "FileNotFoundError" in answer.detail


def test_a_missing_log_directory_is_a_spawn_error_and_spawns_nothing(
    tmp_path: Path,
) -> None:
    popen = FakePopen()

    answer = launch(_entry(), tmp_path / "no-such-supervisor", popen)

    assert isinstance(answer, LaunchError)
    assert answer.failure is LaunchFailure.SPAWN_ERROR
    assert popen.calls == []


def test_an_existing_log_is_a_spawn_error_and_is_left_alone(
    supervisor_dir: Path,
) -> None:
    logs = log_paths(supervisor_dir, ENTRY_ID)
    logs.stderr.write_text("earlier attempt")
    popen = FakePopen()

    answer = launch(_entry(), supervisor_dir, popen)

    assert isinstance(answer, LaunchError)
    assert "FileExistsError" in answer.detail
    assert popen.calls == []
    assert logs.stderr.read_text() == "earlier attempt"
    assert not logs.stdout.exists() or logs.stdout.stat().st_size == 0


def test_unusable_journal_parameters_raise(supervisor_dir: Path) -> None:
    with pytest.raises(ValueError, match="checkout"):
        launch(_entry(checkout=""), supervisor_dir, FakePopen())


def test_reap_drops_exited_confirmed_children_only(supervisor_dir: Path) -> None:
    tracker = LaunchTracker()
    exited_confirmed, exited_unconfirmed, alive = (
        FakeChild(0),
        FakeChild(1),
        FakeChild(None),
    )
    tracker.track("a", exited_confirmed)
    tracker.confirm("a")
    tracker.track("b", exited_unconfirmed)
    tracker.track("c", alive)
    tracker.confirm("c")

    tracker.reap()

    assert tracker.get("a") is None
    assert tracker.get("b") is not None, "its exit still decides the launch"
    assert tracker.get("c") is not None
    assert (exited_confirmed.polls, exited_unconfirmed.polls, alive.polls) == (1, 1, 1)


def test_forget_drops_a_launch_and_ignores_an_unknown_one() -> None:
    tracker = LaunchTracker()
    tracker.track("a", FakeChild())

    tracker.forget("a")
    tracker.forget("never-tracked")

    assert tracker.get("a") is None


def test_launching_the_stub_sq_for_real(
    tmp_path: Path, supervisor_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    checkout = tmp_path / "checkout"
    home.mkdir()
    checkout.mkdir()
    bin_dir = write_sq_stub(tmp_path / "bin")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv(RUN_SECONDS_ENV, "0")

    child = launch(_entry(checkout=str(checkout)), supervisor_dir, subprocess.Popen)
    assert not isinstance(child, LaunchError), child
    tracker = LaunchTracker()
    tracker.track(ENTRY_ID, child)
    tracker.confirm(ENTRY_ID)
    deadline = time.monotonic() + 20
    while tracker.get(ENTRY_ID) is not None and time.monotonic() < deadline:
        tracker.reap()
        time.sleep(0.05)

    assert tracker.get(ENTRY_ID) is None, "the child was never reaped"
    assert stderr_confirms(log_paths(supervisor_dir, ENTRY_ID).stderr, RUN_ID)
