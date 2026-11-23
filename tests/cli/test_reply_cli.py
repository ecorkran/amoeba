"""``amoeba reply``: the three actions, the exits and the usage errors (slice 240,
D4)."""

from __future__ import annotations

from pathlib import Path

from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from cli.message_cli_support import (
    registered,
    registered_member_id,
    result_of,
    run_amoeba,
    send_request,
    stored_rows,
)

HASH = "ab12" * 10


def test_accept_applies_and_prints_the_new_state(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(tmp_path, "reply", "ask-1", "accept", as_json=True)

    assert completed.returncode == EXIT_OK, completed.stderr
    result = result_of(completed)
    assert result["outcome"] == "applied"
    assert result["request"]["state"] == "accepted"
    assert result["request"]["direction"] == "received"
    assert result["request"]["accepted_at"] is not None


def test_accept_text_names_the_state_and_the_request(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(tmp_path, "reply", "ask-1", "accept")

    assert completed.returncode == EXIT_OK
    lines = completed.stdout.splitlines()
    assert lines[1] == "accepted: ask-1"


def test_done_stores_the_text_commit_and_version(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")
    run_amoeba(tmp_path, "reply", "ask-1", "accept")

    completed = run_amoeba(
        tmp_path,
        "reply",
        "ask-1",
        "done",
        "--text",
        "shipped",
        "--commit",
        HASH,
        "--version",
        "v1.0.0",
        as_json=True,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    request = result_of(completed)["request"]
    assert request["state"] == "done"
    assert (request["result"], request["result_commit"], request["result_version"]) == (
        "shipped",
        HASH,
        "v1.0.0",
    )


def test_decline_stores_the_reason(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(
        tmp_path, "reply", "ask-1", "decline", "--text", "not our rules", as_json=True
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    request = result_of(completed)["request"]
    assert (request["state"], request["reason"]) == ("declined", "not our rules")


def test_a_second_accept_exits_one_naming_the_time(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")
    run_amoeba(tmp_path, "reply", "ask-1", "accept")

    completed = run_amoeba(tmp_path, "reply", "ask-1", "accept", as_json=True)

    assert completed.returncode == EXIT_REJECTED
    result = result_of(completed)
    assert result["rejection"] == "already_accepted"
    assert "was already accepted at " in result["problems"][0]
    (row,) = stored_rows("message_rejections")
    assert (row[1], row[4], row[6]) == (
        registered_member_id(),
        "ask-1",
        "already_accepted",
    )


def test_an_unknown_request_exits_one(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(tmp_path, "reply", "nothing", "accept")

    assert completed.returncode == EXIT_REJECTED
    assert completed.stdout.startswith("rejected: unknown_request: ")


def test_decline_without_text_is_rejected_as_malformed(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(tmp_path, "reply", "ask-1", "decline", as_json=True)

    assert completed.returncode == EXIT_REJECTED
    result = result_of(completed)
    assert result["rejection"] == "malformed"
    assert "text is required for decline" in result["problems"][0]


def test_commit_on_accept_is_rejected_as_malformed(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(
        tmp_path, "reply", "ask-1", "accept", "--commit", HASH, as_json=True
    )

    assert completed.returncode == EXIT_REJECTED
    assert "commit is only allowed for done" in result_of(completed)["problems"][0]


def test_an_unknown_action_is_a_usage_error(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(tmp_path, "reply", "ask-1", "reopen")

    assert completed.returncode == EXIT_USAGE
    assert "invalid choice" in completed.stderr


def test_a_cf_failure_is_exit_three(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(tmp_path, "reply", "ask-1", "accept", cf_fixture=None)

    assert completed.returncode == EXIT_ERROR
