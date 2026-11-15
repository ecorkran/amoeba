"""``amoeba inbox``: text, ``-j``, ``--since`` and the exits (slice 240, D7)."""

from __future__ import annotations

from pathlib import Path

from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from cli.message_cli_support import (
    PROJECT_ID,
    registered,
    result_of,
    run_amoeba,
    send_request,
)


def test_an_empty_inbox_says_so_and_gives_the_number_for_next_time(
    tmp_path: Path,
) -> None:
    registered(tmp_path)

    completed = run_amoeba(tmp_path, "inbox")

    assert completed.returncode == EXIT_OK, completed.stderr
    assert completed.stdout == (
        "No requests.\nas_of_seq: 0 (pass it as --since next time)\n"
    )


def test_the_document_has_the_requests_and_the_number_to_pass_back(
    tmp_path: Path,
) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(tmp_path, "inbox", as_json=True)

    assert completed.returncode == EXIT_OK, completed.stderr
    result = result_of(completed)
    assert result["outcome"] == "listed"
    assert result["member"] == PROJECT_ID
    assert result["since"] is None
    assert result["as_of_seq"] == 1
    assert [request["id"] for request in result["requests"]] == ["ask-1"]
    assert result["deliveries"] == []
    assert result["notice"] == QUOTED_DATA_NOTICE


def test_the_text_lists_the_request_below_the_notice(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(tmp_path, "inbox")

    lines = completed.stdout.splitlines()
    assert lines[0] == QUOTED_DATA_NOTICE
    assert lines[1] == "Requests"
    assert "ask-1" in lines[2]
    assert "subject: subject of ask-1" in completed.stdout
    assert lines[-1] == "as_of_seq: 1 (pass it as --since next time)"


def test_since_returns_the_deliveries_after_it(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")
    send_request(tmp_path, "ask-2")

    completed = run_amoeba(tmp_path, "inbox", "--since", "1", as_json=True)

    assert completed.returncode == EXIT_OK, completed.stderr
    result = result_of(completed)
    assert result["since"] == 1
    assert [item["message_id"] for item in result["deliveries"]] == ["ask-2"]
    assert result["deliveries"][0]["event"] == "sent"
    assert [request["id"] for request in result["requests"]] == ["ask-2"]


def test_since_text_lists_the_deliveries(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(tmp_path, "inbox", "--since", "0")

    assert "Deliveries" in completed.stdout
    assert " · sent · ask-1 · " in completed.stdout


def test_nothing_new_after_the_last_number(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(tmp_path, "inbox", "--since", "1")

    assert completed.returncode == EXIT_OK
    assert completed.stdout.startswith("Nothing new.\n")


def test_since_beyond_the_last_record_exits_one(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(tmp_path, "inbox", "--since", "9")

    assert completed.returncode == EXIT_REJECTED
    assert completed.stdout.startswith("rejected: beyond_last_record: ")
    assert "call inbox without since" in completed.stdout


def test_since_must_be_a_whole_number(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(tmp_path, "inbox", "--since", "soon")

    assert completed.returncode == EXIT_USAGE


def test_a_negative_since_is_rejected_as_malformed(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(tmp_path, "inbox", "--since", "-1", as_json=True)

    assert completed.returncode == EXIT_REJECTED
    assert result_of(completed)["rejection"] == "malformed"


def test_a_cf_failure_is_exit_three(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(tmp_path, "inbox", cf_fixture=None)

    assert completed.returncode == EXIT_ERROR
    assert completed.stderr.startswith("error: ContextForgeError")
