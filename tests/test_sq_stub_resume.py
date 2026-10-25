"""The stub ``sq run --resume`` mode: each documented state it can leave."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sq_stub import (
    STUB_STATE_RELATIVE,
    write_outcome_document,
    write_sq_stub,
)
from sq_stub_resume import (
    OUTCOME_PAUSED_AGAIN,
    RESUME_ARGV_LOG_ENV,
    RESUME_CLAIM_SECONDS_ENV,
    RESUME_EXIT_CODE_ENV,
    RESUME_MODE_ENV,
    RESUME_OUTCOME_ENV,
    ResumeMode,
)

RUN_ID = "amoeba-20261025T101500Z-0123456789ab"
OLD_PAUSE = "2026-10-25T10:00:00+00:00"
CHECKPOINT = {"kind": "loop_exhausted", "is_loop": True, "paused_at": OLD_PAUSE}


class Rig:
    """A stub ``sq`` under a temporary ``HOME`` with one paused run."""

    def __init__(self, tmp_path: Path) -> None:
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.argv_log = tmp_path / "argv.jsonl"
        self.stub = write_sq_stub(tmp_path / "bin") / "sq"
        write_outcome_document(
            self.home,
            {
                "run_id": RUN_ID,
                "outcome": "paused",
                "status": "paused",
                "checkpoint": CHECKPOINT,
            },
        )

    def resume(self, *arguments: str, **extra: str) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "HOME": str(self.home),
            RESUME_ARGV_LOG_ENV: str(self.argv_log),
            **extra,
        }
        return subprocess.run(
            [sys.executable, str(self.stub), "run", "--resume", *arguments],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def state(self, run_id: str = RUN_ID) -> dict[str, object]:
        path = self.home / STUB_STATE_RELATIVE / f"{run_id}.json"
        return json.loads(path.read_text())


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def test_a_resume_completes_the_run_by_default(rig: Rig) -> None:
    result = rig.resume(RUN_ID, "--decision", "retry")

    assert result.returncode == 0
    state = rig.state()
    assert state["outcome"] == "completed" and "checkpoint" not in state


def test_a_resume_can_pause_again_with_a_new_paused_at(rig: Rig) -> None:
    result = rig.resume(
        RUN_ID, "--decision", "accept", **{RESUME_OUTCOME_ENV: OUTCOME_PAUSED_AGAIN}
    )

    assert result.returncode == 0
    state = rig.state()
    assert state["outcome"] == "paused"
    checkpoint = state["checkpoint"]
    assert isinstance(checkpoint, dict)
    assert checkpoint["kind"] == "loop_exhausted"
    new_pause = datetime.fromisoformat(str(checkpoint["paused_at"]))
    assert new_pause > datetime.fromisoformat(OLD_PAUSE).astimezone(UTC)


def test_a_refused_resume_exits_two_and_leaves_the_run(rig: Rig) -> None:
    result = rig.resume(
        RUN_ID, "--decision", "accept", **{RESUME_MODE_ENV: ResumeMode.REFUSE.value}
    )

    assert result.returncode == 2
    assert rig.state()["checkpoint"] == CHECKPOINT


def test_exit_before_claim_uses_the_configured_code_and_leaves_the_run(
    rig: Rig,
) -> None:
    result = rig.resume(
        RUN_ID,
        "--decision",
        "retry",
        **{
            RESUME_MODE_ENV: ResumeMode.EXIT_BEFORE_CLAIM.value,
            RESUME_EXIT_CODE_ENV: "7",
        },
    )

    assert result.returncode == 7
    assert rig.state()["outcome"] == "paused"


def test_never_claim_exits_zero_and_leaves_the_run_paused(rig: Rig) -> None:
    result = rig.resume(
        RUN_ID,
        "--decision",
        "retry",
        **{RESUME_MODE_ENV: ResumeMode.NEVER_CLAIM.value},
    )

    assert result.returncode == 0
    assert rig.state()["checkpoint"] == CHECKPOINT


def test_the_claim_waits_for_the_configured_delay(rig: Rig) -> None:
    started = time.monotonic()
    result = rig.resume(
        RUN_ID, "--decision", "retry", **{RESUME_CLAIM_SECONDS_ENV: "0.4"}
    )

    assert result.returncode == 0
    assert time.monotonic() - started >= 0.4


def test_a_missing_run_exits_one(rig: Rig) -> None:
    result = rig.resume("no-such-run", "--decision", "retry")

    assert result.returncode == 1


def test_a_run_that_is_not_paused_exits_one(rig: Rig) -> None:
    assert rig.resume(RUN_ID, "--decision", "retry").returncode == 0

    again = rig.resume(RUN_ID, "--decision", "retry")

    assert again.returncode == 1


@pytest.mark.parametrize(
    "arguments",
    [
        [RUN_ID],
        [RUN_ID, "--decision", "handled"],
        [RUN_ID, "--decision", "retry", "--bogus", "x"],
    ],
)
def test_bad_arguments_exit_two(rig: Rig, arguments: list[str]) -> None:
    assert rig.resume(*arguments).returncode == 2


def test_the_argv_log_holds_the_instructions_element_unchanged(rig: Rig) -> None:
    text = 'line one\n  "quoted" é, two spaces  \nend'

    rig.resume(RUN_ID, "--decision", "retry", "--instructions", text)

    [line] = rig.argv_log.read_text(encoding="utf-8").splitlines()
    assert json.loads(line) == [
        "run",
        "--resume",
        RUN_ID,
        "--decision",
        "retry",
        "--instructions",
        text,
    ]
