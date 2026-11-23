"""``amoeba add --wake-command`` and ``--no-wake-command``, and what ``list members``
shows (slice 244, D1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from amoeba.cli.exit_codes import EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from amoeba.cli.main import main
from amoeba.cli.parser import build_parser
from amoeba.cli.registration_arguments import add_document
from cli.cli_support import (
    request_file,
    result_of,
    run_amoeba,
    write_config,
)
from cli.requests_support import Repos

COMMAND = "wake-agent --max-seconds 60"
FIELD = "wake_command"
TEXT_LINE = "  wake command:\n    " + COMMAND + "\n"


def _members(tmp_path: Path) -> dict[str, Any]:
    document: dict[str, Any] = result_of(
        run_amoeba(tmp_path, "list", "members", as_json=True)
    )
    return document


def test_the_flags_build_the_request_field() -> None:
    parser = build_parser()

    set_document = add_document(
        parser.parse_args(["add", "--wake-command", COMMAND]), lambda _: None
    )
    clear_document = add_document(
        parser.parse_args(["add", "--no-wake-command"]), lambda _: None
    )
    omitted = add_document(parser.parse_args(["add"]), lambda _: None)

    assert set_document == {FIELD: COMMAND}
    assert clear_document == {FIELD: None}
    assert FIELD not in omitted


@pytest.mark.parametrize(
    "flags",
    [
        ["--wake-command", COMMAND, "--no-wake-command"],
        ["--file", "x.yaml", "--wake-command", COMMAND],
        ["--file", "x.yaml", "--no-wake-command"],
    ],
)
def test_a_bad_flag_combination_is_a_usage_error(flags: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["add", *flags])

    assert raised.value.code == EXIT_USAGE


def test_wake_command_sets_and_no_wake_command_clears(tmp_path: Path) -> None:
    write_config()

    added = run_amoeba(tmp_path, "add", "--wake-command", COMMAND)
    with_command = run_amoeba(tmp_path, "list", "members")
    json_with = _members(tmp_path)
    cleared = run_amoeba(tmp_path, "add", "--no-wake-command")
    after = run_amoeba(tmp_path, "list", "members")

    assert added.returncode == EXIT_OK, added.stderr
    assert TEXT_LINE in with_command.stdout
    assert json_with["members"][0][FIELD] == COMMAND
    assert cleared.returncode == EXIT_OK
    assert "wake command" not in after.stdout
    assert _members(tmp_path)["members"][0][FIELD] is None


def test_a_member_without_a_command_has_no_line_and_a_null_in_json(
    tmp_path: Path,
) -> None:
    write_config()
    run_amoeba(tmp_path, "add")

    text = run_amoeba(tmp_path, "list", "members").stdout

    assert "wake command" not in text
    assert _members(tmp_path)["members"][0][FIELD] is None


def test_project_with_a_wake_command_is_malformed(tmp_path: Path) -> None:
    """A command is set from its own checkout (261 D7): ``--project`` names a member,
    not a checkout, so it cannot carry one."""
    write_config()
    repos = Repos(tmp_path)
    repos.run(repos.forge, "add", "--program", "demo")

    refused = repos.run(
        repos.squadron,
        "add",
        "--project",
        repos.forge.name,
        "--wake-command",
        COMMAND,
        expect=EXIT_REJECTED,
    )

    assert refused["outcome"] == "rejected"
    assert [problem["code"] for problem in refused["problems"]] == ["malformed"]
    assert "its own checkout" in refused["problems"][0]["detail"]
    members = repos.run(repos.guide, "list", "members")["members"]
    assert {row["name"]: row[FIELD] for row in members} == {repos.forge.name: None}


def test_file_sets_leaves_and_clears_through_the_bulk_key(tmp_path: Path) -> None:
    write_config()
    document: dict[str, Any] = {"program": "demo", "members": [{FIELD: COMMAND}]}

    def apply(members: list[dict[str, Any]]) -> None:
        path = request_file(tmp_path, {"program": "demo", "members": members})
        completed = run_amoeba(tmp_path, "add", "--file", str(path))
        assert completed.returncode == EXIT_OK, completed.stderr + completed.stdout

    apply(document["members"])
    assert _members(tmp_path)["members"][0][FIELD] == COMMAND
    apply([{"rules_paths": ["CLAUDE.md"]}])
    assert _members(tmp_path)["members"][0][FIELD] == COMMAND
    apply([{FIELD: None}])
    assert _members(tmp_path)["members"][0][FIELD] is None


def test_an_unsplittable_text_exits_nonzero_naming_the_field(tmp_path: Path) -> None:
    write_config()

    completed = run_amoeba(tmp_path, "add", "--wake-command", "agent 'unbalanced")

    assert completed.returncode == EXIT_REJECTED
    assert FIELD in completed.stdout


def test_add_help_says_the_command_runs_unattended(tmp_path: Path) -> None:
    completed = run_amoeba(tmp_path, "add", "--help")

    text = " ".join(completed.stdout.split())
    assert "unattended" in text
    assert "privileges" in text
    assert "plain text" in text
    assert "its own cost or time cap" in text
