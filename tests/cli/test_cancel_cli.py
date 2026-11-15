"""``amoeba cancel``: the exits and what is stored (slice 240, D3, D4)."""

from __future__ import annotations

from pathlib import Path

from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED
from cli.message_cli_support import (
    registered,
    result_of,
    run_amoeba,
    send_request,
    stored_rows,
)


def test_cancel_ends_the_request_with_its_reason(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(
        tmp_path, "cancel", "ask-1", "--reason", "no longer needed", as_json=True
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    result = result_of(completed)
    assert result["outcome"] == "cancelled"
    assert result["request"]["state"] == "cancelled"
    assert result["request"]["reason"] == "no longer needed"


def test_cancel_text_names_the_request(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")

    completed = run_amoeba(tmp_path, "cancel", "ask-1")

    assert completed.returncode == EXIT_OK
    assert completed.stdout.splitlines()[1] == "cancelled: ask-1"


def test_a_repeated_cancel_exits_one_naming_the_state(tmp_path: Path) -> None:
    registered(tmp_path)
    send_request(tmp_path, "ask-1")
    run_amoeba(tmp_path, "cancel", "ask-1")

    completed = run_amoeba(tmp_path, "cancel", "ask-1", as_json=True)

    assert completed.returncode == EXIT_REJECTED
    result = result_of(completed)
    assert result["rejection"] == "not_applicable"
    assert "cancelled" in result["problems"][0]
    assert len(stored_rows("message_rejections")) == 1


def test_an_unknown_id_exits_one(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(tmp_path, "cancel", "nothing")

    assert completed.returncode == EXIT_REJECTED
    assert completed.stdout.startswith("rejected: unknown_request: ")


def test_a_cf_failure_is_exit_three(tmp_path: Path) -> None:
    registered(tmp_path)

    completed = run_amoeba(tmp_path, "cancel", "ask-1", cf_fixture=None)

    assert completed.returncode == EXIT_ERROR
