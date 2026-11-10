"""``start_child`` and ``terminate_group`` with real short subprocesses
(slice 223, task 5.2). The kept ``spawn``'s own behavior is tested with it."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from process_containment import contained_popen

from amoeba.operations.processes import (
    WaitableChild,
    start_child,
    terminate_group,
)
from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs, stderr_tail

PYTHON = sys.executable
WAIT_SECONDS = 20.0


def _logs(directory: Path, name: str = "child") -> LaunchLogs:
    return LaunchLogs(
        stdout=directory / f"{name}.stdout.log", stderr=directory / f"{name}.stderr.log"
    )


def _start(argv: list[str], tmp_path: Path, logs: LaunchLogs) -> WaitableChild:
    child = start_child(argv, tmp_path, logs, popen=contained_popen)
    assert not isinstance(child, LaunchError), child
    return child


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_the_logs_are_written_even_when_their_directory_does_not_exist(
    tmp_path: Path,
) -> None:
    logs = _logs(tmp_path / "not" / "yet", "run")

    child = _start(
        [PYTHON, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
        tmp_path,
        logs,
    )

    assert child.wait(timeout=WAIT_SECONDS) == 0
    assert logs.stdout.read_text(encoding="utf-8") == "out\n"
    assert logs.stderr.read_text(encoding="utf-8") == "err\n"


def test_a_second_start_to_the_same_log_path_is_a_launch_error(tmp_path: Path) -> None:
    logs = _logs(tmp_path)
    first = _start([PYTHON, "-c", "print('first')"], tmp_path, logs)
    first.wait(timeout=WAIT_SECONDS)

    second = start_child(
        [PYTHON, "-c", "print('second')"], tmp_path, logs, popen=contained_popen
    )

    assert isinstance(second, LaunchError)
    assert second.failure is LaunchFailure.SPAWN_ERROR
    assert logs.stdout.read_text(encoding="utf-8") == "first\n"


def test_an_unrunnable_executable_is_a_launch_error(tmp_path: Path) -> None:
    result = start_child(
        [str(tmp_path / "no-such-program")],
        tmp_path,
        _logs(tmp_path),
        popen=contained_popen,
    )

    assert isinstance(result, LaunchError)


def test_a_log_directory_that_cannot_be_made_is_a_launch_error(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")

    result = start_child(
        [PYTHON, "-c", "pass"], tmp_path, _logs(blocker / "sub"), popen=contained_popen
    )

    assert isinstance(result, LaunchError)


def test_the_child_runs_in_the_given_directory_with_empty_stdin(tmp_path: Path) -> None:
    logs = _logs(tmp_path)
    code = "import os, sys; print(os.getcwd()); print(repr(sys.stdin.read()))"

    child = _start([PYTHON, "-c", code], tmp_path, logs)

    assert child.wait(timeout=WAIT_SECONDS) == 0
    cwd, stdin = logs.stdout.read_text(encoding="utf-8").splitlines()
    assert Path(cwd).resolve() == tmp_path.resolve()
    assert stdin == "''"


def test_wait_times_out_on_a_sleeping_child(tmp_path: Path) -> None:
    child = _start(
        [PYTHON, "-c", "import time; time.sleep(60)"], tmp_path, _logs(tmp_path)
    )
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            child.wait(timeout=0.2)
        assert child.poll() is None
    finally:
        terminate_group(child)


def test_terminate_group_kills_the_child_and_its_own_child(tmp_path: Path) -> None:
    logs = _logs(tmp_path)
    code = (
        "import subprocess, sys, time\n"
        "sleeper = [sys.executable, '-c', 'import time; time.sleep(60)']\n"
        "grandchild = subprocess.Popen(sleeper)\n"
        "print(grandchild.pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    child = _start([PYTHON, "-c", code], tmp_path, logs)
    deadline = time.monotonic() + WAIT_SECONDS
    while not logs.stdout.read_text(encoding="utf-8").strip():
        assert time.monotonic() < deadline, "the child never printed its child's pid"
        time.sleep(0.05)
    grandchild = int(logs.stdout.read_text(encoding="utf-8").split()[0])
    assert _alive(grandchild)

    terminate_group(child)

    assert child.poll() is not None
    deadline = time.monotonic() + WAIT_SECONDS
    while _alive(grandchild):
        assert time.monotonic() < deadline, "the grandchild outlived the group stop"
        time.sleep(0.05)


def test_terminate_group_on_an_exited_child_just_returns(tmp_path: Path) -> None:
    child = _start([PYTHON, "-c", "pass"], tmp_path, _logs(tmp_path))
    child.wait(timeout=WAIT_SECONDS)

    terminate_group(child)

    assert child.poll() == 0


def test_the_kept_stderr_tail_returns_the_last_lines_of_a_childs_stderr(
    tmp_path: Path,
) -> None:
    logs = _logs(tmp_path)
    code = "import sys\nfor n in range(2000): print(f'line {n}', file=sys.stderr)\n"

    child = _start([PYTHON, "-c", code], tmp_path, logs)
    child.wait(timeout=WAIT_SECONDS)

    tail = stderr_tail(logs.stderr)
    assert tail.rstrip().endswith("line 1999")
    assert "line 0\n" not in tail
