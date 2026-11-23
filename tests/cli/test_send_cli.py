"""``amoeba send``: text, ``-j``, every exit code and the body sources (slice 240)."""

from __future__ import annotations

from pathlib import Path

from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from cli.message_cli_support import (
    PROJECT_NAME,
    registered,
    registered_member_id,
    result_of,
    run_amoeba,
    send_request,
    stored_rows,
)


def test_send_prints_the_result_document(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = send_request(tmp_path, "ask-1")

    assert completed.returncode == EXIT_OK, completed.stderr
    result = result_of(completed)
    assert result["outcome"] == "sent"
    assert result["rejection"] is None
    assert result["notice"] == QUOTED_DATA_NOTICE
    assert result["request"]["id"] == "ask-1"
    assert result["request"]["from_member"] == registered_member_id()
    assert result["request"]["state"] == "open"
    assert result["request"]["direction"] == "sent"
    assert len(stored_rows("messages")) == 1


def test_send_text_starts_with_the_notice_then_the_request(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = send_request(tmp_path, "ask-1", as_json=False)

    assert completed.returncode == EXIT_OK, completed.stderr
    lines = completed.stdout.splitlines()
    assert lines[0] == QUOTED_DATA_NOTICE
    assert lines[1] == "sent: ask-1"
    assert "subject: subject of ask-1" in completed.stdout
    assert "body: body of ask-1" in completed.stdout


def test_sending_the_same_request_again_is_unchanged_with_exit_zero(
    tmp_path: Path,
) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = send_request(tmp_path, "ask-1")

    assert completed.returncode == EXIT_OK, completed.stderr
    assert result_of(completed)["outcome"] == "unchanged"
    assert len(stored_rows("messages")) == 1


def test_a_rejected_send_exits_one_and_is_recorded(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = send_request(tmp_path, "ask-1", "--parent", "nowhere")

    assert completed.returncode == EXIT_REJECTED, completed.stderr
    result = result_of(completed)
    assert result["outcome"] == "rejected"
    assert result["rejection"] == "parent_unknown"
    assert result["request"] is None
    assert stored_rows("messages") == []
    (row,) = stored_rows("message_rejections")
    assert row[1] == registered_member_id()
    assert "parent_unknown" in row


def test_a_rejected_send_prints_the_code_and_the_problem(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = send_request(tmp_path, "ask-1", "--parent", "nowhere", as_json=False)

    assert completed.returncode == EXIT_REJECTED
    assert completed.stdout.startswith("rejected: parent_unknown: ")
    assert "nowhere" in completed.stdout


def test_a_missing_flag_is_rejected_as_malformed_not_a_usage_error(
    tmp_path: Path,
) -> None:
    registered(tmp_path)

    completed = run_amoeba(
        tmp_path,
        "send",
        "--to",
        PROJECT_NAME,
        "--subject",
        "s",
        "--body",
        "b",
        as_json=True,
    )

    assert completed.returncode == EXIT_REJECTED, completed.stderr
    result = result_of(completed)
    assert result["rejection"] == "malformed"
    assert "id" in result["problems"][0]


def test_the_body_comes_from_stdin_with_a_dash(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(
        tmp_path,
        "send",
        "--id",
        "from-stdin",
        "--to",
        PROJECT_NAME,
        "--subject",
        "s",
        "--body-file",
        "-",
        stdin=b"a body\nover two lines\n",
        as_json=True,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert result_of(completed)["request"]["body"] == "a body\nover two lines"


def test_the_body_comes_from_a_file(tmp_path: Path) -> None:
    registered(tmp_path)
    body = tmp_path / "body.txt"
    body.write_text("text from a file", encoding="utf-8")

    completed = run_amoeba(
        tmp_path,
        "send",
        "--id",
        "from-file",
        "--to",
        PROJECT_NAME,
        "--subject",
        "s",
        "--body-file",
        str(body),
        as_json=True,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert result_of(completed)["request"]["body"] == "text from a file"


def test_an_unreadable_body_file_is_a_usage_error(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(
        tmp_path,
        "send",
        "--id",
        "x",
        "--to",
        PROJECT_NAME,
        "--subject",
        "s",
        "--body-file",
        str(tmp_path / "missing.txt"),
    )

    assert completed.returncode == EXIT_USAGE
    assert "cannot read" in completed.stderr


def test_body_with_body_file_is_a_usage_error(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = send_request(tmp_path, "ask-1", "--body-file", "-")

    assert completed.returncode == EXIT_USAGE
    assert "not allowed with argument" in completed.stderr
    assert stored_rows("messages") == []


def test_a_cf_failure_is_exit_three_and_writes_nothing(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(
        tmp_path,
        "send",
        "--id",
        "ask-1",
        "--to",
        PROJECT_NAME,
        "--subject",
        "s",
        "--body",
        "b",
        cf_fixture=None,
    )

    assert completed.returncode == EXIT_ERROR
    assert completed.stderr.startswith("error: ContextForgeError")
    assert stored_rows("messages") == []
    assert stored_rows("message_rejections") == []
