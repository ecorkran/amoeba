"""``amoeba send --note``: both recipients, text and ``-j``, refusals and exits
(slice 243, D1)."""

from __future__ import annotations

from pathlib import Path

from amoeba.cli.exit_codes import EXIT_OK, EXIT_REJECTED
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from cli.cli_support import write_config
from cli.message_cli_support import (
    registered,
    registered_member_id,
    result_of,
    run_amoeba,
    send_note,
    send_request,
    stored_rows,
)
from cli.requests_support import Repos

PROGRAM = "demo"


def test_note_to_a_member_prints_the_note_and_leaves_no_request(
    tmp_path: Path,
) -> None:
    registered(tmp_path)

    completed = send_note(tmp_path, "news-1")

    assert completed.returncode == EXIT_OK, completed.stderr
    result = result_of(completed)
    assert result["outcome"] == "sent"
    assert result["request"] is None
    assert result["note"]["id"] == "news-1"
    assert result["note"]["from_member"] == registered_member_id()
    assert result["note"]["to_program"] is None
    assert result["notice"] == QUOTED_DATA_NOTICE
    ((message_id, kind, *_rest),) = stored_rows("messages")
    assert (message_id, kind) == ("news-1", "note")


def test_the_text_starts_with_the_notice_then_the_note(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = send_note(tmp_path, "news-1", as_json=False)

    lines = completed.stdout.splitlines()
    assert lines[0] == QUOTED_DATA_NOTICE
    assert lines[1] == "sent: news-1"
    assert "subject: subject of news-1" in completed.stdout
    assert "body: body of news-1" in completed.stdout


def test_a_note_to_a_program_reaches_the_other_members_not_the_sender(
    tmp_path: Path,
) -> None:
    write_config()
    repos = Repos(tmp_path)
    for project in repos.projects:
        repos.run(project, "add", "--program", PROGRAM)

    sent = repos.run(
        repos.squadron,
        "send",
        "--note",
        "--id",
        "news-1",
        "--to-program",
        PROGRAM,
        "--subject",
        "freeze",
        "--body",
        "no merges after noon",
    )

    assert sent["outcome"] == "sent"
    assert sent["note"]["to_member"] is None
    assert sent["note"]["to_program"] == PROGRAM
    for reader in (repos.forge, repos.guide):
        assert [n["id"] for n in repos.run(reader, "inbox")["notes"]] == ["news-1"]
    assert repos.run(repos.squadron, "inbox")["notes"] == []


def test_without_note_send_is_a_request_exactly_as_before(tmp_path: Path) -> None:
    registered(tmp_path)

    result = result_of(send_request(tmp_path, "ask-1"))

    assert result["request"]["id"] == "ask-1"
    assert result["note"] is None
    ((_id, kind, *_rest),) = stored_rows("messages")
    assert kind == "request"


def test_to_program_without_note_is_rejected_with_exit_one(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(
        tmp_path,
        "send",
        "--id",
        "ask-1",
        "--to-program",
        PROGRAM,
        "--subject",
        "s",
        "--body",
        "b",
        as_json=True,
    )

    assert completed.returncode == EXIT_REJECTED
    result = result_of(completed)
    assert result["rejection"] == "malformed"
    assert "to_program" in result["problems"][0]


def test_neither_recipient_is_malformed_with_exit_one(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(
        tmp_path,
        "send",
        "--note",
        "--id",
        "news-1",
        "--subject",
        "s",
        "--body",
        "b",
        as_json=True,
    )

    assert completed.returncode == EXIT_REJECTED
    assert result_of(completed)["rejection"] == "malformed"
    assert stored_rows("messages") == []


def test_a_note_to_a_program_with_no_one_else_is_rejected_and_printed(
    tmp_path: Path,
) -> None:
    write_config()
    assert run_amoeba(tmp_path, "add", "--program", PROGRAM).returncode == EXIT_OK

    completed = send_note(tmp_path, "news-1", "--to-program", PROGRAM, as_json=False)

    assert completed.returncode == EXIT_REJECTED
    assert completed.stdout.startswith("rejected: unknown_recipient: ")
    assert "no one else" in completed.stdout


def test_the_same_note_again_is_unchanged_with_exit_zero(tmp_path: Path) -> None:
    registered(tmp_path)
    send_note(tmp_path, "news-1")

    completed = send_note(tmp_path, "news-1")

    assert completed.returncode == EXIT_OK, completed.stderr
    assert result_of(completed)["outcome"] == "unchanged"
    assert len(stored_rows("messages")) == 1
    assert len(stored_rows("deliveries")) == 1


def test_a_note_cut_in_the_send_text_says_the_json_result_is_whole(
    tmp_path: Path,
) -> None:
    registered(tmp_path)
    long_body = " ".join(["word"] * 60)

    text = send_note(tmp_path, "news-1", "--body", long_body, as_json=False).stdout
    whole = result_of(send_note(tmp_path, "news-1", "--body", long_body))

    assert "A note cut with … is whole in the -j result of this call." in text
    assert whole["note"]["body"] == long_body
