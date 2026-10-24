"""``run_cf``: expected external failures are answers; both streams are kept."""

from __future__ import annotations

import subprocess
from typing import Any

from amoeba.runner.cf_call import CfCallFailed, run_cf

ARGV = ["cf", "list", "initiatives", "--json"]
TIMEOUT_SECONDS = 5.0


def test_a_completed_process_is_returned_with_both_streams() -> None:
    seen: dict[str, Any] = {}

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(argv=argv, **kwargs)
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="the error")

    completed = run_cf(ARGV, run, TIMEOUT_SECONDS)

    assert isinstance(completed, subprocess.CompletedProcess)
    assert (completed.returncode, completed.stdout, completed.stderr) == (
        1,
        "",
        "the error",
    )
    assert seen["argv"] == ARGV
    assert seen["timeout"] == TIMEOUT_SECONDS
    assert seen["capture_output"] is True
    assert seen["stdin"] == subprocess.DEVNULL


def test_a_timeout_is_an_answer_naming_the_command() -> None:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(argv, TIMEOUT_SECONDS)

    answer = run_cf(ARGV, run, TIMEOUT_SECONDS)

    assert answer == CfCallFailed(f"`{' '.join(ARGV)}` timed out after 5.0s")


def test_a_missing_executable_is_an_answer() -> None:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("no cf")

    answer = run_cf(ARGV, run, TIMEOUT_SECONDS)

    assert isinstance(answer, CfCallFailed)
    assert "could not run" in answer.detail
    assert "no cf" in answer.detail
