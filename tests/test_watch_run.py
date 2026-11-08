"""``watch_run`` reports the launcher exit and kills a launcher that outlives it.

These cases stub ``poll_run`` and launch a short child process, so the exit-grace
and kill paths run with no ``sq`` and no spend.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

import live_harness
import pytest
from live_harness import PipelineRun, watch_run

from amoeba.upstream.squadron.run_outcome import (
    PollFailure,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
)

RUN_ID = "run-test"
EXITS_AT_ONCE = [sys.executable, "-c", "print('launcher output')"]
OUTLIVES_THE_WAIT = [sys.executable, "-c", "import time; time.sleep(60)"]


def _stub_poll(monkeypatch: pytest.MonkeyPatch, answer: RunPoll) -> None:

    def poll_run(run_id: str, *, timeout_seconds: float) -> RunPoll:
        return answer

    monkeypatch.setattr(live_harness, "poll_run", poll_run)
    monkeypatch.setattr(live_harness, "POLL_INTERVAL_SECONDS", 0.01)


def _outcome(outcome: RunOutcome) -> RunOutcomeDocument:
    return RunOutcomeDocument(run_id=RUN_ID, outcome=outcome)


def _watch(
    argv: list[str], tmp_path: Path, timeout: float, grace: float
) -> PipelineRun:
    return watch_run(argv, RUN_ID, tmp_path, timeout, grace)


def test_launcher_that_exits_within_the_grace_reports_its_own_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _stub_poll(monkeypatch, _outcome(RunOutcome.COMPLETED))
    result = _watch(EXITS_AT_ONCE, tmp_path, timeout=30, grace=30)
    assert result.exit_code == 0
    assert "launcher output" in result.sq_output
    assert result.poll == _outcome(RunOutcome.COMPLETED)


def test_launcher_still_running_after_the_grace_is_killed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _stub_poll(monkeypatch, _outcome(RunOutcome.COMPLETED))
    result = _watch(OUTLIVES_THE_WAIT, tmp_path, timeout=30, grace=0.2)
    assert result.exit_code == -signal.SIGKILL
    assert result.poll == _outcome(RunOutcome.COMPLETED)


def test_deadline_leaves_a_poll_failure_and_kills_the_launcher(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _stub_poll(monkeypatch, _outcome(RunOutcome.NOT_FOUND))
    result = _watch(OUTLIVES_THE_WAIT, tmp_path, timeout=0.3, grace=0.0)
    assert isinstance(result.poll, PollFailure)
    assert "did not finish" in result.poll.reason
    assert result.exit_code == -signal.SIGKILL


def test_launcher_that_exits_before_the_run_is_found_is_a_poll_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _stub_poll(monkeypatch, _outcome(RunOutcome.NOT_FOUND))
    result = _watch(EXITS_AT_ONCE, tmp_path, timeout=30, grace=0.0)
    assert isinstance(result.poll, PollFailure)
    assert "before run" in result.poll.reason
    assert result.exit_code == 0


LEAVES_AN_ORPHAN = [
    sys.executable,
    "-c",
    "import pathlib, subprocess, sys; "
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
    "pathlib.Path('orphan.pid').write_text(str(child.pid))",
]


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        # No such process: the kill reached it and it has been reaped.
        return False
    return True


def test_child_of_a_launcher_that_exited_by_itself_is_killed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _stub_poll(monkeypatch, _outcome(RunOutcome.COMPLETED))
    result = _watch(LEAVES_AN_ORPHAN, tmp_path, timeout=30, grace=30)
    assert result.exit_code == 0
    orphan_pid = int((tmp_path / "orphan.pid").read_text())
    deadline = time.monotonic() + 5
    while _is_alive(orphan_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _is_alive(orphan_pid)
