"""The fake ``sq`` replays a recording and records ``sq run`` calls (slice 223, 2.3)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fake_sq import (
    PAUSED_AGENT_QUESTION,
    fake_poller,
    poll_result,
    recorded_listing,
    recorded_warning,
    write_fake_sq,
)

from amoeba.upstream.squadron.run_outcome import RunOutcome


def _sq(fake_dir: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(fake_dir / "sq"), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_runs_wait_prints_the_recording_and_exits_with_its_code(
    tmp_path: Path,
) -> None:
    fake = write_fake_sq(
        tmp_path,
        waits={"demo-1": PAUSED_AGENT_QUESTION},
        run_exit_code=0,
        run_stderr="",
    )

    result = _sq(fake.directory, "runs", "wait", "demo-1", "--timeout", "0", "--json")

    assert result.returncode == 3
    document = json.loads(result.stdout)
    assert document["run_id"] == "demo-1"
    assert document["checkpoint"]["kind"] == "agent_question"
    assert document["checkpoint"]["question"].startswith("What is the maximum")


def test_an_unregistered_run_is_not_found(tmp_path: Path) -> None:
    fake = write_fake_sq(tmp_path, waits={}, run_exit_code=0, run_stderr="")

    result = _sq(fake.directory, "runs", "wait", "nope", "--json")

    assert result.returncode == 5
    assert json.loads(result.stdout) == {"run_id": "nope", "outcome": "not_found"}


def test_a_sq_run_call_is_recorded_with_instructions_as_one_element(
    tmp_path: Path,
) -> None:
    fake = write_fake_sq(tmp_path, waits={}, run_exit_code=7, run_stderr="locked")
    text = "You asked: why?\nAnswer: 'because' \"so\""

    result = _sq(fake.directory, "run", "--resume", "r1", "--instructions", text)

    assert result.returncode == 7
    assert result.stderr.strip() == "locked"
    assert fake.run_calls() == [["run", "--resume", "r1", "--instructions", text]]


def test_an_unsupported_command_exits_two(tmp_path: Path) -> None:
    fake = write_fake_sq(tmp_path, waits={}, run_exit_code=0, run_stderr="")

    assert _sq(fake.directory, "models").returncode == 2


def test_the_poller_returns_its_script_then_repeats_the_last() -> None:
    paused = poll_result(PAUSED_AGENT_QUESTION, "r1")
    poller = fake_poller({"r1": [paused]})

    assert poller("r1", timeout_seconds=1) == paused
    assert poller("r1", timeout_seconds=1) == paused
    assert poller.calls == ["r1", "r1"]
    assert paused.outcome is RunOutcome.PAUSED


def test_runs_list_replays_the_recording_and_records_its_argv(tmp_path: Path) -> None:
    fake = write_fake_sq(
        tmp_path,
        waits={},
        run_exit_code=0,
        run_stderr="",
        runs_list=recorded_listing(stderr=recorded_warning()),
    )

    result = _sq(fake.directory, "runs", "list", "--json")

    assert result.returncode == 0
    assert result.stdout == recorded_listing().stdout
    assert "unavailable pipelines" in result.stderr
    assert fake.list_calls() == [["runs", "list", "--json"]]
    assert fake.run_calls() == []


def test_an_sq_without_a_listing_exits_2_for_runs_list(tmp_path: Path) -> None:
    fake = write_fake_sq(tmp_path, waits={}, run_exit_code=0, run_stderr="")

    result = _sq(fake.directory, "runs", "list", "--json")

    assert result.returncode == 2
    assert result.stdout == ""
