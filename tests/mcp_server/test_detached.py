"""The detached ``handle_pause`` start (slice 226, D6, task 4.1)."""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio
import pytest
from cf_fixtures import DEFAULT_WORKTREE, write_fake_cf
from fake_sq import write_fake_sq
from user_configs import example_config_text

from amoeba import wiring
from amoeba.cli.parser import build_parser
from amoeba.config.home import StateLayout, calls_log_dir, config_path, state_layout
from amoeba.mcp import detached
from amoeba.mcp.detached import (
    AmoebaScriptMissing,
    HandlePauseNotStarted,
    StartedCall,
    resolve_amoeba_script,
    start_handle_pause,
)
from amoeba.mcp.tools import RequestError
from amoeba.operations.names import OperationName
from amoeba.operations.prune import prune
from amoeba.store.store import Store
from amoeba.upstream.squadron.launch import LaunchLogs

WAIT_SECONDS = 20
SYSTEM_PATH = "/usr/bin:/bin"
FAKE_PID = 4242
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)


class _FakeChild:
    pid = FAKE_PID

    def poll(self) -> int | None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        return 0


class _Starts:
    """A stand-in for ``wiring.start_child`` that records each start."""

    def __init__(self) -> None:
        self.calls: list[tuple[Sequence[str], Path, LaunchLogs]] = []

    def __call__(self, argv: Sequence[str], cwd: Path, logs: LaunchLogs) -> _FakeChild:
        self.calls.append((argv, cwd, logs))
        return _FakeChild()


def _start(raw: dict[str, object]) -> StartedCall:
    async def run() -> StartedCall:
        return await start_handle_pause(raw)

    return anyio.run(run)


def _wait_exited(pid: int) -> int:
    """Wait for a child of this process to exit, and return its exit status."""
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            reaped, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            # Expected: another part of the process already reaped it.
            return 0
        if reaped == pid:
            return os.waitstatus_to_exitcode(status)
        time.sleep(0.02)
    raise AssertionError(f"child {pid} did not exit")


def test_the_argv_parses_through_the_cli_parser_to_the_input_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    starts = _Starts()
    monkeypatch.setattr(wiring, "start_child", starts)
    monkeypatch.setattr(detached, "resolve_amoeba_script", lambda: Path("/x/amoeba"))

    for run_id in ("run-1", "-starts-with-a-dash"):
        _start({"run_id": run_id, "directory": str(tmp_path)})

    for (argv, _cwd, _logs), run_id in zip(
        starts.calls, ("run-1", "-starts-with-a-dash"), strict=True
    ):
        assert argv[0] == "/x/amoeba"
        parsed = build_parser().parse_args(list(argv[1:]))
        assert parsed.command == OperationName.HANDLE_PAUSE.cli_name
        assert parsed.operation is OperationName.HANDLE_PAUSE
        assert parsed.json is True
        assert parsed.run_id == run_id


def test_the_child_starts_in_the_given_directory_and_the_receipt_names_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    starts = _Starts()
    monkeypatch.setattr(wiring, "start_child", starts)
    monkeypatch.setattr(detached, "resolve_amoeba_script", lambda: Path("/x/amoeba"))

    receipt = _start({"run_id": "run-1", "directory": str(tmp_path)})

    ((_argv, cwd, logs),) = starts.calls
    assert cwd == tmp_path
    assert receipt.operation is OperationName.HANDLE_PAUSE
    assert (receipt.pid, receipt.cwd) == (FAKE_PID, tmp_path)
    assert (receipt.stdout_log, receipt.stderr_log) == (logs.stdout, logs.stderr)
    log_directory = state_layout().logs_dir / "mcp" / "handle_pause"
    assert receipt.stdout_log.parent == receipt.stderr_log.parent == log_directory
    assert receipt.stdout_log.name.endswith(".stdout.log")
    assert receipt.stderr_log.name.endswith(".stderr.log")


@pytest.mark.parametrize(
    ("raw", "field"),
    [
        ({"run_id": "r", "directory": "relative/path"}, "directory"),
        ({"run_id": "r"}, "directory"),
        ({"directory": "/tmp"}, "run_id"),
    ],
    ids=["relative-directory", "no-directory", "no-run-id"],
)
def test_a_request_that_is_not_a_run_and_a_directory_starts_nothing(
    monkeypatch: pytest.MonkeyPatch, raw: dict[str, object], field: str
) -> None:
    starts = _Starts()
    monkeypatch.setattr(wiring, "start_child", starts)
    monkeypatch.setattr(detached, "resolve_amoeba_script", lambda: Path("/x/amoeba"))

    with pytest.raises(RequestError, match=field):
        _start(raw)

    assert starts.calls == []


def _fake_amoeba(directory: Path) -> Path:
    """A script that records how it was started, waits for a go-file, then prints
    one JSON document, as the real ``handle_pause`` does."""
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "amoeba"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "here = Path(sys.argv[0]).parent\n"
        "(here / 'seen.json').write_text(json.dumps("
        "{'argv': sys.argv[1:], 'cwd': os.getcwd()}))\n"
        f"deadline = time.monotonic() + {WAIT_SECONDS}\n"
        "while not (here / 'go').exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.02)\n"
        "print(json.dumps({'outcome': 'skipped'}))\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_the_start_returns_while_the_child_runs_and_the_log_gets_its_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _fake_amoeba(tmp_path / "fake-bin")
    monkeypatch.setattr(detached, "resolve_amoeba_script", lambda: script)
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    receipt = _start({"run_id": "-run", "directory": str(checkout)})

    # Still running: the go-file does not exist yet.
    assert os.waitpid(receipt.pid, os.WNOHANG) == (0, 0)
    (script.parent / "go").touch()
    assert _wait_exited(receipt.pid) == 0
    assert json.loads(receipt.stdout_log.read_text(encoding="utf-8")) == {
        "outcome": "skipped"
    }
    seen = json.loads((script.parent / "seen.json").read_text(encoding="utf-8"))
    assert seen["argv"] == ["handle-pause", "--json", "--", "-run"]
    assert Path(seen["cwd"]).resolve() == checkout.resolve()


def test_the_real_cli_child_writes_its_calls_log_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bin_dir = tmp_path / "bin"
    write_fake_sq(bin_dir, waits={}, run_exit_code=0, run_stderr="")
    write_fake_cf(bin_dir, DEFAULT_WORKTREE)
    home = tmp_path / "home"
    (home / ".config" / "squadron" / "runs").mkdir(parents=True)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{SYSTEM_PATH}")
    monkeypatch.setenv("HOME", str(home))
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")

    receipt = _start({"run_id": "no-such-run", "directory": str(tmp_path)})
    _wait_exited(receipt.pid)

    lines = [
        json.loads(line)
        for day_file in sorted(calls_log_dir().glob("*.jsonl"))
        for line in day_file.read_text(encoding="utf-8").splitlines()
    ]
    assert [line["run_id"] for line in lines] == ["no-such-run"]
    assert lines[0]["directory"] == str(tmp_path)


def _layout(root: Path) -> StateLayout:
    return StateLayout(
        state_home=root,
        store_path=root / "amoeba.sqlite3",
        answering_dir=root / "answering",
        logs_dir=root / "logs",
        calls_log_dir=root / "logs" / "calls",
        legacy_home=None,
    )


def _log(layout: StateLayout, name: str, days_old: float) -> Path:
    path = layout.logs_dir / "mcp" / "handle_pause" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    stamp = (NOW - timedelta(days=days_old)).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def test_an_old_detached_log_is_pruned_with_its_emptied_directories(
    tmp_path: Path,
) -> None:
    layout = _layout(tmp_path / "state")
    old = _log(layout, "old.stdout.log", 40)

    with Store.open(layout.store_path) as store:
        prune(store, layout, NOW, 30)

    assert not old.exists()
    assert not (layout.logs_dir / "mcp").exists()


def test_a_young_detached_log_stays(tmp_path: Path) -> None:
    layout = _layout(tmp_path / "state")
    old = _log(layout, "old.stdout.log", 40)
    young = _log(layout, "young.stdout.log", 5)

    with Store.open(layout.store_path) as store:
        prune(store, layout, NOW, 30)

    assert not old.exists()
    assert young.exists()


def test_the_resolved_script_is_the_one_beside_the_interpreter() -> None:
    assert resolve_amoeba_script() == Path(sys.executable).parent / "amoeba"


def test_a_missing_script_raises_naming_its_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "executable", str(tmp_path / "bin" / "python"))

    with pytest.raises(AmoebaScriptMissing, match=str(tmp_path / "bin" / "amoeba")):
        resolve_amoeba_script()


def test_an_unwritable_log_directory_is_reported_as_a_start_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(detached, "resolve_amoeba_script", lambda: Path("/x/amoeba"))
    # ``logs`` is a file, so the log directories cannot be made under it.
    state_layout().logs_dir.parent.mkdir(parents=True, exist_ok=True)
    state_layout().logs_dir.write_text("not a directory", encoding="utf-8")

    with pytest.raises(HandlePauseNotStarted, match="Error"):
        _start({"run_id": "r", "directory": str(tmp_path)})
