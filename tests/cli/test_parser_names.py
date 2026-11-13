"""The CLI's subcommands are exactly the operations' names (slice 226, D3)."""

from __future__ import annotations

from amoeba.cli.main import build_parser
from amoeba.operations.names import OperationName


def _subcommand_names() -> set[str]:
    parser = build_parser()
    # argparse offers no public list of subparsers; its subparsers action is the
    # one whose choices are the registered commands.
    choices: set[str] = set()
    for action in parser._actions:  # pyright: ignore[reportPrivateUsage]
        action_choices = getattr(action, "choices", None)
        if isinstance(action_choices, dict):
            choices.update(str(key) for key in action_choices)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return choices


def test_the_parser_registers_one_subcommand_per_operation_name() -> None:
    assert _subcommand_names() == {name.value for name in OperationName}


def test_the_operation_names_are_the_eight_the_contract_lists() -> None:
    assert {name.value for name in OperationName} == {
        "set_up",
        "handle_pause",
        "answer",
        "status",
        "decisions",
        "mark_read",
        "dismiss",
        "retract",
    }
