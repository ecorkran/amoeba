"""The CLI's commands come from ``OperationName.cli_name`` (slice 229, D1, task 9.4)."""

from __future__ import annotations

import argparse

import pytest

from amoeba.cli.parser import build_parser
from amoeba.cli.registration_arguments import list_document
from amoeba.mcp.tools import TOOLS
from amoeba.operations.list_view import SUBJECT_ALIASES, ListRequest, ListSubject
from amoeba.operations.names import OperationName

#: A command that is a second name for another: no operation and no tool of its own.
ALIASES = {"remove": OperationName.RM}


def _commands() -> dict[str, argparse.ArgumentParser]:
    """The registered commands by name, aliases included."""
    # argparse offers no public list of subparsers; its subparsers action is the
    # one whose choices are the registered commands.
    for action in build_parser()._actions:  # pyright: ignore[reportPrivateUsage]
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            return dict(choices)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    raise AssertionError("the parser has no subcommands")


def test_every_operation_has_one_command_by_its_cli_name_and_nothing_else() -> None:
    names = set(_commands())

    assert names - set(ALIASES) == {name.cli_name for name in OperationName}


def test_every_operation_has_a_tool_row_by_its_value_and_nothing_else() -> None:
    assert [tool.name for tool in TOOLS].count(OperationName.HANDLE_PAUSE) == 1
    assert {tool.name.value for tool in TOOLS} == {name.value for name in OperationName}


def test_cli_names_are_the_values_with_dashes() -> None:
    assert OperationName.HANDLE_PAUSE.cli_name == "handle-pause"
    assert OperationName.MARK_READ.cli_name == "mark-read"
    assert OperationName.RM.cli_name == "rm"
    assert all("_" not in name.cli_name for name in OperationName)


def test_the_operation_names_are_the_ones_the_contract_lists() -> None:
    assert {name.value for name in OperationName} == {
        "add",
        "rm",
        "list",
        "handle_pause",
        "answer",
        "status",
        "decisions",
        "mark_read",
        "dismiss",
        "retract",
        "report_release",
        "changes",
    }


def test_remove_is_an_alias_of_rm() -> None:
    parser = build_parser()

    by_alias = parser.parse_args(["remove", "some-member"])
    by_name = parser.parse_args(["rm", "some-member"])

    assert by_alias.operation is by_name.operation is OperationName.RM
    assert by_alias.members == by_name.members == ["some-member"]


@pytest.mark.parametrize(
    ("typed", "subject"),
    [
        *((value.value, value) for value in ListSubject),
        *SUBJECT_ALIASES.items(),
    ],
)
def test_list_takes_each_subject_in_singular_and_plural(
    typed: str, subject: ListSubject
) -> None:
    arguments = build_parser().parse_args(["list", typed])

    document = list_document(arguments)
    assert arguments.operation is OperationName.LIST
    assert document == {"subject": typed}
    assert ListRequest.model_validate(document).subject is subject


@pytest.mark.parametrize(
    "old_name",
    ["set_up", "handle_pause", "mark_read"],  # old-name-case
)
def test_an_old_command_name_exits_two_with_the_valid_names_listed(
    old_name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args([old_name])

    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert f"invalid choice: '{old_name}'" in error
    for name in OperationName:
        assert name.cli_name in error


def test_every_command_takes_json_after_its_name() -> None:
    parser = build_parser()
    minimal = {
        "add": ["add"],
        "rm": ["rm"],
        "list": ["list"],
        "handle-pause": ["handle-pause", "r"],
        "answer": ["answer", "r", "--text", "t"],
        "status": ["status"],
        "decisions": ["decisions"],
        "mark-read": ["mark-read", "--through", "1"],
        "dismiss": ["dismiss", "r", "--reason", "x"],
        "retract": ["retract", "1", "--reason", "x"],
        "report-release": ["report-release"],
        "changes": ["changes"],
    }

    assert set(minimal) == {name.cli_name for name in OperationName}
    for argv in minimal.values():
        assert parser.parse_args([*argv, "-j"]).json is True
        assert parser.parse_args([*argv, "--json"]).json is True
        assert parser.parse_args(argv).json is False
