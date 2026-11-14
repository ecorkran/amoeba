"""``amoeba rm``: text and ``-j``, the guards and the exit codes (slice 229, D6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from store.question_support import NOW, claimed_question

from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from amoeba.cli.main import main
from amoeba.config.home import store_path
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from cli.cli_support import (
    PROJECT_ID,
    PROJECT_NAME,
    result_of,
    run_amoeba,
    write_config,
)

KEY = QuestionKey("run-open", "2026-11-14T06:48:00+00:00")


def _registered(tmp_path: Path) -> None:
    write_config()
    assert run_amoeba(tmp_path, "add").returncode == EXIT_OK


def test_rm_with_no_argument_removes_this_repo_and_says_so(tmp_path: Path) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, "rm")

    assert completed.returncode == EXIT_OK, completed.stderr
    assert completed.stdout == f"removed\n  removed member {PROJECT_NAME}\n"


def test_rm_json_prints_the_result_document(tmp_path: Path) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, "rm", as_json=True)

    result = result_of(completed)
    assert result["outcome"] == "applied"
    assert result["changes"] == [f"removed member {PROJECT_ID}"]


@pytest.mark.parametrize("command", ["rm", "remove"])
def test_a_member_is_removed_by_name_and_remove_is_the_same_command(
    tmp_path: Path, command: str
) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, command, PROJECT_NAME)

    assert completed.stdout == f"removed\n  removed member {PROJECT_NAME}\n"


def test_a_member_is_removed_by_id(tmp_path: Path) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, "rm", PROJECT_ID)

    assert completed.returncode == EXIT_OK
    assert completed.stdout.startswith("removed\n")


def test_a_repeat_is_unchanged(tmp_path: Path) -> None:
    _registered(tmp_path)
    run_amoeba(tmp_path, "rm")

    completed = run_amoeba(tmp_path, "rm")

    assert completed.returncode == EXIT_OK
    assert completed.stdout == "unchanged\n"


def test_a_repo_that_was_never_registered_is_not_a_member(tmp_path: Path) -> None:
    write_config()

    completed = run_amoeba(tmp_path, "rm")

    assert completed.returncode == EXIT_REJECTED
    assert completed.stdout.startswith("rejected: not_a_member: ")


def test_open_questions_refuse_and_print_the_commands_that_clear_them(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)
    with Store.open(store_path()) as store, store.write() as transaction:
        insert_question(
            transaction, claimed_question(KEY, member_id=PROJECT_ID), now=NOW
        )

    completed = run_amoeba(tmp_path, "rm")

    assert completed.returncode == EXIT_REJECTED
    lines = completed.stdout.splitlines()
    assert lines[0].startswith("rejected: member_has_open_questions: ")
    assert f"    {KEY.run_id} at {KEY.paused_at}" in lines
    assert any(line.startswith(f"      amoeba answer {KEY.run_id} ") for line in lines)
    assert any(line.startswith(f"      amoeba dismiss {KEY.run_id} ") for line in lines)


def test_a_directory_with_no_project_and_no_name_is_not_a_project(
    tmp_path: Path,
) -> None:
    write_config()

    completed = run_amoeba(tmp_path, "rm", cf_fixture="outside_any_project")

    assert completed.returncode == EXIT_REJECTED
    assert completed.stdout.startswith("rejected: not_a_project: ")


def test_a_failing_cf_exits_three(tmp_path: Path) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, "rm", cf_fixture=None)

    assert completed.returncode == EXIT_ERROR
    assert "error: ContextForgeError" in completed.stderr


@pytest.mark.parametrize("pair", ["no-separator", ":consumer", "provider:"])
def test_a_malformed_pair_exits_two(pair: str) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["rm", "--pair", pair])

    assert raised.value.code == EXIT_USAGE
