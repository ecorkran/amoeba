"""``amoeba status``, ``decisions`` and ``mark-read`` as real subprocesses
(slice 224, 4.1).

A fake ``sq`` (replaying the real ``runs list`` recording) and a fake ``cf`` are first
on ``PATH``; ``HOME`` is a temporary directory holding the run file; ``AMOEBA_HOME`` is
the autouse temporary home, so nothing touches the developer's real home.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from cf_fixtures import DEFAULT_WORKTREE, fixture_document, write_fake_cf_with_projects
from fake_sq import (
    RUN_FILE,
    SQUADRON_FIXTURES,
    FakeListing,
    recorded_listing,
    recorded_warning,
    write_fake_sq,
)
from live_environment import process_environment
from process_containment import contained_popen
from store.decision_support import at, automatic_answer, seed_programs
from user_configs import example_config_text

from amoeba.cli.main import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from amoeba.config.home import config_path, store_path
from amoeba.store.models import QuestionKey
from amoeba.store.store import Store

AMOEBA = Path(sys.executable).with_name("amoeba")
RUN_TIMEOUT_SECONDS = 60
SYSTEM_PATH = "/usr/bin:/bin"
PROJECT_ID: str = fixture_document(DEFAULT_WORKTREE)["id"]
ASKED = QuestionKey("run-1", "2026-11-10T09:00:00+00:00")


def _write_config() -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")


def _run(
    tmp_path: Path,
    *arguments: str,
    listing: FakeListing | None,
    as_json: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ``amoeba``; ``as_json`` adds ``-j`` after the command name."""
    if as_json and arguments and not arguments[0].startswith("-"):
        arguments = (arguments[0], "-j", *arguments[1:])
    bin_dir = tmp_path / "bin"
    write_fake_sq(bin_dir, waits={}, run_exit_code=0, run_stderr="", runs_list=listing)
    write_fake_cf_with_projects(bin_dir, DEFAULT_WORKTREE)
    home = tmp_path / "home"
    runs = home / ".config" / "squadron" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    shutil.copy(SQUADRON_FIXTURES / RUN_FILE, runs / "any-run.json")
    environment = process_environment(
        os.environ,
        PATH=f"{bin_dir}{os.pathsep}{SYSTEM_PATH}",
        HOME=str(home),
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


def _seed_one_answer() -> int:
    """The member of the default worktree in one program, with one automatic answer."""
    with Store.open(store_path()) as store:
        seed_programs(store)
        with store.write() as transaction:
            transaction.execute(
                "UPDATE members SET project_id = ? WHERE project_id = 'member-core'",
                (PROJECT_ID,),
            )
        return automatic_answer(store, ASKED, PROJECT_ID, 1)


def test_status_prints_json_and_exits_zero(tmp_path: Path) -> None:
    _write_config()
    _seed_one_answer()

    completed = _run(
        tmp_path, "status", listing=recorded_listing(stderr=recorded_warning())
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    result = _result(completed)
    assert result["outcome"] == "listed"
    programs = {program["program"]: program for program in result["programs"]}
    (member,) = programs["trading"]["members"]
    assert member["member"] == {"id": PROJECT_ID, "name": "amoeba"}
    kinds = {entry["checkpoint_kind"] for entry in result["unplaced_runs"]}
    assert "awaits_human" in kinds


def test_status_prints_text_without_json(tmp_path: Path) -> None:
    _write_config()
    _seed_one_answer()

    completed = _run(
        tmp_path,
        "status",
        listing=recorded_listing(stderr=recorded_warning()),
        as_json=False,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert completed.stdout.startswith("Unplaced runs\n")
    assert "awaits_human" not in completed.stdout  # the text names the reason instead
    assert not completed.stdout.lstrip().startswith("{")


def test_status_with_an_unknown_program_exits_one(tmp_path: Path) -> None:
    _write_config()
    _seed_one_answer()

    completed = _run(
        tmp_path, "status", "--program", "nope", listing=recorded_listing()
    )

    assert completed.returncode == EXIT_REJECTED
    result = _result(completed)
    assert result["rejection"] == "unknown_program"
    assert "trading" in result["problems"][0]


def test_status_with_an_sq_that_lacks_runs_list_exits_three_naming_the_command(
    tmp_path: Path,
) -> None:
    _write_config()
    _seed_one_answer()

    completed = _run(tmp_path, "status", listing=None)

    assert completed.returncode == EXIT_ERROR
    assert completed.stdout == ""
    assert completed.stderr.startswith("error: SquadronError: ")
    assert "sq runs list --json" in completed.stderr


def test_status_without_a_config_exits_three(tmp_path: Path) -> None:
    completed = _run(tmp_path, "status", listing=recorded_listing())

    assert completed.returncode == EXIT_ERROR
    assert "ConfigError" in completed.stderr


def test_decisions_exits_zero_with_records_and_a_read_through(tmp_path: Path) -> None:
    seq = _seed_one_answer()

    completed = _run(tmp_path, "decisions", listing=None)

    assert completed.returncode == EXIT_OK, completed.stderr
    result = _result(completed)
    assert [record["seq"] for record in result["records"]] == [seq]
    assert result["read_through"] == seq
    assert result["records"][0]["member"] == {"id": PROJECT_ID, "name": "amoeba"}


def test_decisions_exits_zero_with_no_records_and_needs_no_config(
    tmp_path: Path,
) -> None:
    completed = _run(tmp_path, "decisions", listing=None)

    assert completed.returncode == EXIT_OK, completed.stderr
    result = _result(completed)
    assert result["records"] == []
    assert result["read_through"] is None


def test_decisions_with_a_since_and_a_program_narrows(tmp_path: Path) -> None:
    seq = _seed_one_answer()

    since = _run(tmp_path, "decisions", "--since", at(0).isoformat(), listing=None)
    other = _run(tmp_path, "decisions", "--program", "tools", listing=None)

    assert [r["seq"] for r in _result(since)["records"]] == [seq]
    assert _result(since)["read_through"] is None
    assert _result(other)["records"] == []


def test_a_malformed_since_exits_one(tmp_path: Path) -> None:
    completed = _run(
        tmp_path, "decisions", "--since", "2026-11-10T12:00:00", listing=None
    )

    assert completed.returncode == EXIT_REJECTED
    assert _result(completed)["rejection"] == "malformed"


def test_mark_read_moves_then_decisions_is_empty(tmp_path: Path) -> None:
    seq = _seed_one_answer()

    moved = _run(tmp_path, "mark-read", "--through", str(seq), listing=None)
    after = _run(tmp_path, "decisions", listing=None)

    assert moved.returncode == EXIT_OK, moved.stderr
    assert _result(moved)["outcome"] == "moved"
    assert _result(after)["records"] == []
    assert _result(after)["marker"] == seq


def test_mark_read_and_decisions_print_text_without_json(tmp_path: Path) -> None:
    seq = _seed_one_answer()

    listed = _run(tmp_path, "decisions", listing=None, as_json=False)
    moved = _run(
        tmp_path, "mark-read", "--through", str(seq), listing=None, as_json=False
    )

    assert listed.stdout.startswith("1 answer (marker at 0)\n")
    assert f"  amoeba mark-read --through {seq}\n" in listed.stdout
    assert moved.stdout == f"moved: marker 0 -> {seq}\n"


def test_mark_read_beyond_the_last_record_exits_one(tmp_path: Path) -> None:
    completed = _run(tmp_path, "mark-read", "--through", "999999", listing=None)

    assert completed.returncode == EXIT_REJECTED
    assert _result(completed)["rejection"] == "beyond_last_record"


def test_a_negative_through_exits_one_as_malformed(tmp_path: Path) -> None:
    completed = _run(tmp_path, "mark-read", "--through", "-1", listing=None)

    assert completed.returncode == EXIT_REJECTED
    assert _result(completed)["rejection"] == "malformed"


def test_mark_read_without_through_exits_two(tmp_path: Path) -> None:
    completed = _run(tmp_path, "mark-read", listing=None)

    assert completed.returncode == EXIT_USAGE
    assert "--through" in completed.stderr


def test_the_help_texts_print_usage(tmp_path: Path) -> None:
    for command in ("status", "decisions", "mark-read"):
        completed = _run(tmp_path, command, "--help", listing=None)

        assert completed.returncode == EXIT_OK
        assert completed.stdout.startswith(f"usage: amoeba {command}")
