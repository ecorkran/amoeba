"""``amoeba rm``: text and ``-j``, the guards and the exit codes (slice 229, D6)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from store.question_support import NOW, claimed_question
from store_open import open_local_store

from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from amoeba.cli.main import main
from amoeba.config.home import store_path
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from cli.cli_support import (
    PROJECT_NAME,
    PROJECT_PATH,
    result_of,
    run_amoeba,
    write_config,
)

KEY = QuestionKey("run-open", "2026-11-14T06:48:00+00:00")


def _registered(tmp_path: Path) -> None:
    write_config()
    assert run_amoeba(tmp_path, "add").returncode == EXIT_OK


def _member_id() -> str:
    """The registered member's own id (not Context Forge's)."""
    with sqlite3.connect(store_path()) as connection:
        row = connection.execute("SELECT project_id FROM members").fetchone()
    return str(row[0])


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
    assert result["changes"] == [f"removed member {PROJECT_NAME}"]


@pytest.mark.parametrize("command", ["rm", "remove"])
def test_a_member_is_removed_by_name_and_remove_is_the_same_command(
    tmp_path: Path, command: str
) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, command, PROJECT_NAME)

    assert completed.stdout == f"removed\n  removed member {PROJECT_NAME}\n"


def test_a_member_is_removed_by_id(tmp_path: Path) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, "rm", _member_id())

    assert completed.returncode == EXIT_OK
    assert completed.stdout.startswith("removed\n")


def test_a_repeat_by_id_is_unchanged_and_by_name_is_not_a_member(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)
    member_id = _member_id()
    run_amoeba(tmp_path, "rm", member_id)

    by_id = run_amoeba(tmp_path, "rm", member_id)
    by_name = run_amoeba(tmp_path, "rm", PROJECT_NAME)

    assert by_id.returncode == EXIT_OK
    assert by_id.stdout == "unchanged\n"
    assert by_name.returncode == EXIT_REJECTED
    assert by_name.stdout.startswith("rejected: not_a_member: ")


def test_a_repo_that_was_never_registered_is_not_a_member(tmp_path: Path) -> None:
    write_config()

    completed = run_amoeba(tmp_path, "rm")

    assert completed.returncode == EXIT_REJECTED
    assert completed.stdout.startswith("rejected: not_a_member: ")


def test_open_questions_refuse_and_print_the_commands_that_clear_them(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)
    member_id = _member_id()
    with open_local_store(store_path()) as store, store.write() as transaction:
        insert_question(
            transaction, claimed_question(KEY, member_id=member_id), now=NOW
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


def test_checkout_reaches_the_request_and_removes_it_leaving_the_member(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, "rm", "--checkout", PROJECT_PATH, as_json=True)

    assert completed.returncode == EXIT_OK, completed.stderr
    assert result_of(completed)["changes"] == [f"removed checkout {PROJECT_PATH}"]
    listed = result_of(run_amoeba(tmp_path, "list", "members", as_json=True))
    (member,) = listed["members"]
    assert (member["name"], member["checkouts"]) == (PROJECT_NAME, [])


def test_checkout_with_no_such_path_is_rejected_and_lists_the_paths(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)

    text = run_amoeba(tmp_path, "rm", "--checkout", "/nowhere")
    document = result_of(
        run_amoeba(tmp_path, "rm", "--checkout", "/nowhere", as_json=True)
    )

    assert text.returncode == EXIT_REJECTED
    assert text.stdout.startswith("rejected: not_a_checkout: ")
    (problem,) = document["problems"]
    assert problem["code"] == "not_a_checkout"
    assert PROJECT_PATH in problem["detail"]
