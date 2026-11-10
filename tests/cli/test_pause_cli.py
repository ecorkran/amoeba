"""``amoeba handle_pause`` and ``amoeba answer`` as real subprocesses (slice 223, 8.2).

A fake ``sq`` and ``cf`` are first on ``PATH``; ``HOME`` is a temporary directory that
holds ``.config/squadron/runs/<run_id>.json`` (copied from the recording), so nothing
reads the developer's real run files. ``AMOEBA_HOME`` is the autouse temporary home.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import DEFAULT_WORKTREE, fixture_document, write_fake_cf
from fake_sq import (
    COMPLETED,
    PAUSED_AGENT_QUESTION,
    RUN_FILE,
    SQUADRON_FIXTURES,
    FakeSq,
    poll_result,
    write_fake_sq,
)
from live_environment import process_environment
from process_containment import contained_popen
from user_configs import example_config_text

from amoeba.answering.values import DeclineReason
from amoeba.cli.main import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE, main
from amoeba.config.home import config_path, store_path
from amoeba.store.models import MemberSettings, QuestionKey
from amoeba.store.programs import upsert_member, upsert_program
from amoeba.store.questions import NewQuestion, insert_question, settle_waiting
from amoeba.store.store import Store

AMOEBA = Path(sys.executable).with_name("amoeba")
RUN_TIMEOUT_SECONDS = 60
RUN = "demo-run"
PROJECT_ID: str = fixture_document(DEFAULT_WORKTREE)["id"]
PAUSE = poll_result(PAUSED_AGENT_QUESTION, RUN)
SYSTEM_PATH = "/usr/bin:/bin"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def _home(tmp_path: Path) -> Path:
    """A ``HOME`` holding the run file the real ``sq`` would have written."""
    home = tmp_path / "home"
    runs = home / ".config" / "squadron" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    shutil.copy(SQUADRON_FIXTURES / RUN_FILE, runs / f"{RUN}.json")
    return home


def _write_config() -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")


def _fake_sq(tmp_path: Path, waits: dict[str, str]) -> FakeSq:
    return write_fake_sq(tmp_path / "bin", waits=waits, run_exit_code=0, run_stderr="")


def _run(
    tmp_path: Path, *arguments: str, with_sq: bool = True
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    write_fake_cf(bin_dir, DEFAULT_WORKTREE)
    if not with_sq:
        (bin_dir / "sq").unlink(missing_ok=True)
    environment = process_environment(
        os.environ,
        PATH=f"{bin_dir}{os.pathsep}{SYSTEM_PATH}",
        HOME=str(_home(tmp_path)),
        AMOEBA_HOME=os.environ["AMOEBA_HOME"],
    )
    child = contained_popen(
        [str(AMOEBA), *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        env=environment,
    )
    stdout, stderr = child.communicate(timeout=RUN_TIMEOUT_SECONDS)
    return subprocess.CompletedProcess(
        child.args, child.returncode, stdout.decode(), stderr.decode()
    )


def _result(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(completed.stdout)
    return document


def _seed_waiting_question() -> QuestionKey:
    assert PAUSE.checkpoint is not None
    key = QuestionKey(RUN, PAUSE.checkpoint.paused_at_text or "")
    with Store.open(store_path()) as store, store.write() as transaction:
        upsert_program(
            transaction,
            program_id="demo",
            concept_member=None,
            concept_path=None,
            now=NOW,
        )
        upsert_member(
            transaction,
            program_id="demo",
            settings=MemberSettings(
                project_id=PROJECT_ID,
                rules_paths=("CLAUDE.md",),
                authorize_allow=(),
                authorize_deny=(),
            ),
            now=NOW,
        )
        insert_question(
            transaction,
            NewQuestion(
                key=key,
                member_id=PROJECT_ID,
                question="What is the limit?",
                checkout="/tmp",
                slice_label="none",
                source_commit="abc",
                passages=None,
                answering_run_id="a-1",
                waiting_reason=None,
                waiting_detail=None,
            ),
            now=NOW,
        )
        settle_waiting(
            transaction,
            key,
            "a-1",
            reason=DeclineReason.CHECK_SAID_NO,
            detail="no",
            evidence=None,
            now=NOW,
        )
    return key


def test_handle_pause_skips_a_run_that_is_not_paused_with_exit_zero(
    tmp_path: Path,
) -> None:
    _write_config()
    _fake_sq(tmp_path, {RUN: COMPLETED})

    completed = _run(tmp_path, "handle_pause", RUN)

    assert completed.returncode == EXIT_OK, completed.stderr
    result = _result(completed)
    assert result["outcome"] == "skipped"
    assert result["skip_reason"] == "not_paused"


def test_handle_pause_skips_a_project_in_no_program_with_exit_zero(
    tmp_path: Path,
) -> None:
    _write_config()
    _fake_sq(tmp_path, {RUN: PAUSED_AGENT_QUESTION})

    completed = _run(tmp_path, "handle_pause", RUN)

    assert completed.returncode == EXIT_OK, completed.stderr
    assert _result(completed)["skip_reason"] == "not_in_program"


def test_an_operational_failure_exits_three_with_the_error_on_stderr(
    tmp_path: Path,
) -> None:
    _write_config()
    # No ``sq`` at all: Squadron cannot be asked, which is not "not mine".
    completed = _run(tmp_path, "handle_pause", RUN, with_sq=False)

    assert completed.returncode == EXIT_ERROR
    assert completed.stdout == ""
    assert completed.stderr.startswith("error: SquadronError: ")


def test_a_missing_config_exits_three_naming_the_file(tmp_path: Path) -> None:
    _fake_sq(tmp_path, {RUN: COMPLETED})

    completed = _run(tmp_path, "handle_pause", RUN)

    assert completed.returncode == EXIT_ERROR
    assert "ConfigError" in completed.stderr
    assert str(config_path()) in completed.stderr


def test_answer_with_no_question_is_rejected_with_exit_one(tmp_path: Path) -> None:
    _write_config()
    _fake_sq(tmp_path, {})

    completed = _run(tmp_path, "answer", RUN, "--text", "Use 250.")

    assert completed.returncode == EXIT_REJECTED, completed.stderr
    result = _result(completed)
    assert result["outcome"] == "rejected"
    assert result["rejection"] == "no_such_question"
    assert "handle_pause" in result["problems"][0]


def test_answer_records_and_reports_the_resume_with_exit_zero(tmp_path: Path) -> None:
    _write_config()
    fake = _fake_sq(tmp_path, {RUN: PAUSED_AGENT_QUESTION})
    key = _seed_waiting_question()

    completed = _run(tmp_path, "answer", RUN, "--text", "Use 250 lines.")

    assert completed.returncode == EXIT_OK, completed.stderr
    result = _result(completed)
    assert result["outcome"] == "recorded"
    assert result["key"] == {"run_id": RUN, "paused_at": key.paused_at}
    # The fake ``sq run --resume`` exits at once and the run is still at the pause.
    assert result["resume"]["outcome"] == "refused"
    ((first, *_rest),) = fake.run_calls()
    assert first == "run"
    assert fake.run_calls()[0][1:3] == ["--resume", RUN]
    assert (
        fake.run_calls()[0][-1]
        == "You asked: What is the limit?\nAnswer: Use 250 lines."
    )


def test_answer_with_a_paused_at_names_the_pause(tmp_path: Path) -> None:
    _write_config()
    _fake_sq(tmp_path, {RUN: PAUSED_AGENT_QUESTION})
    key = _seed_waiting_question()

    completed = _run(
        tmp_path, "answer", RUN, "--paused-at", key.paused_at, "--text", "Use 250."
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert _result(completed)["key"]["paused_at"] == key.paused_at


@pytest.mark.parametrize(
    "arguments",
    [("answer", RUN), ("handle_pause",), ("answer", "--text", "x"), ("no_such",)],
)
def test_a_usage_error_exits_two(tmp_path: Path, arguments: tuple[str, ...]) -> None:
    completed = _run(tmp_path, *arguments)

    assert completed.returncode == EXIT_USAGE
    assert completed.stdout == ""
    assert "usage:" in completed.stderr


def test_help_prints_usage_for_both_commands(tmp_path: Path) -> None:
    for command in ("handle_pause", "answer"):
        completed = _run(tmp_path, command, "--help")

        assert completed.returncode == EXIT_OK
        assert completed.stdout.startswith("usage: amoeba " + command)


def test_main_in_process_rejects_an_answer_with_no_question(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_config()

    code = main(["answer", RUN, "--text", "Use 250."])

    assert code == EXIT_REJECTED
    printed = json.loads(capsys.readouterr().out)
    assert printed["outcome"] == "rejected"
    assert printed["rejection"] == "no_such_question"


def test_main_in_process_exits_two_on_a_usage_error() -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["answer", RUN])

    assert stopped.value.code == EXIT_USAGE
