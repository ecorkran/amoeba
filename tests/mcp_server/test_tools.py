"""The tool table: names, modes, advice, schemas and argument preparation
(slice 226, D2, D5, D12).

This directory is not named ``mcp``: a test package of that name would shadow the
SDK when pytest puts ``tests/`` on the import path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.cli.parser import build_parser
from amoeba.mcp.tools import (
    READ_ADVICE,
    TOOLS,
    WRITE_ADVICE,
    RequestError,
    RunMode,
    ToolSpec,
    input_schema,
    prepare_arguments,
)
from amoeba.operations.answer import AnswerRequest
from amoeba.operations.names import OperationName

DIRECTORY_TOOLS = {
    OperationName.ADD,
    OperationName.RM,
    OperationName.LIST,
    OperationName.STATUS,
    OperationName.HANDLE_PAUSE,
}
READ_TOOLS = {OperationName.STATUS, OperationName.DECISIONS, OperationName.LIST}
#: A CLI command that is a second name for another, so it has no tool of its own.
CLI_ALIASES = {"remove"}


def _spec(name: OperationName) -> ToolSpec:
    (spec,) = (tool for tool in TOOLS if tool.name is name)
    return spec


def _subcommands() -> set[str]:
    choices: set[str] = set()
    for action in build_parser()._actions:  # pyright: ignore[reportPrivateUsage]
        action_choices = getattr(action, "choices", None)
        if isinstance(action_choices, dict):
            choices.update(str(key) for key in action_choices)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return choices


def test_tool_names_are_the_operation_names_and_the_cli_commands_their_cli_names() -> (
    None
):
    names = [tool.name.value for tool in TOOLS]

    assert len(names) == len(set(names))
    assert set(names) == {name.value for name in OperationName}
    assert {name.cli_name for name in OperationName} == _subcommands() - CLI_ALIASES


def test_the_tool_table_has_add_rm_and_list_and_no_set_up() -> None:
    names = {tool.name.value for tool in TOOLS}

    assert {"add", "rm", "list"} <= names
    assert "set_up" not in names


def test_exactly_these_tools_take_a_directory() -> None:
    assert {tool.name for tool in TOOLS if tool.takes_directory} == DIRECTORY_TOOLS


def test_handle_pause_is_the_only_detached_tool() -> None:
    detached = {tool.name for tool in TOOLS if tool.mode is RunMode.DETACHED}

    assert detached == {OperationName.HANDLE_PAUSE}


def test_every_in_process_tool_has_advice_and_handle_pause_has_none() -> None:
    for tool in TOOLS:
        if tool.mode is RunMode.IN_PROCESS:
            expected = READ_ADVICE if tool.name in READ_TOOLS else WRITE_ADVICE
            assert tool.timeout_advice == expected, tool.name
        else:
            assert tool.timeout_advice is None, tool.name


def test_the_two_advice_texts_differ_and_name_their_way_out() -> None:
    assert READ_ADVICE != WRITE_ADVICE
    assert "shell" in READ_ADVICE
    assert "status" in WRITE_ADVICE and "decisions" in WRITE_ADVICE


@pytest.mark.parametrize("tool", TOOLS, ids=lambda tool: tool.name.value)
def test_each_schema_is_an_object_schema(tool: ToolSpec) -> None:
    assert input_schema(tool)["type"] == "object"


@pytest.mark.parametrize("tool", TOOLS, ids=lambda tool: tool.name.value)
def test_directory_is_required_exactly_for_the_three_directory_tools(
    tool: ToolSpec,
) -> None:
    schema = input_schema(tool)

    needs_directory = tool.name in DIRECTORY_TOOLS
    assert ("directory" in schema.get("required", [])) is needs_directory
    assert ("directory" in schema["properties"]) is needs_directory
    if needs_directory:
        assert schema["properties"]["directory"]["type"] == "string"


def test_the_answer_schema_is_the_request_models_unchanged_with_no_door() -> None:
    schema = input_schema(_spec(OperationName.ANSWER))

    assert schema == AnswerRequest.model_json_schema()
    assert "via" not in schema["properties"]


def test_a_valid_directory_is_removed_and_the_rest_passes_through() -> None:
    spec = _spec(OperationName.STATUS)

    document, directory = prepare_arguments(
        spec, {"directory": "/tmp/repo", "program": "trading", "unknown": [1]}
    )

    assert directory == Path("/tmp/repo")
    assert document == {"program": "trading", "unknown": [1]}


@pytest.mark.parametrize(
    "arguments",
    [None, {}, {"program": "x"}, {"directory": 5}, {"directory": "repo"}],
    ids=["no-arguments", "empty", "missing", "not-a-string", "relative"],
)
def test_a_missing_or_unusable_directory_is_refused_naming_the_field(
    arguments: dict[str, object] | None,
) -> None:
    for name in DIRECTORY_TOOLS:
        with pytest.raises(RequestError, match="directory"):
            prepare_arguments(_spec(name), arguments)


def test_invalid_values_reach_the_operation_untouched() -> None:
    spec = _spec(OperationName.ADD)

    document, directory = prepare_arguments(
        spec, {"directory": "/tmp/repo", "program": 5, "zzz": None}
    )

    assert directory == Path("/tmp/repo")
    assert document == {"program": 5, "zzz": None}


def test_a_tool_without_a_directory_strips_and_ignores_nothing() -> None:
    spec = _spec(OperationName.DECISIONS)
    arguments: dict[str, object] = {"since": "x", "directory": "relative", "zzz": 1}

    document, directory = prepare_arguments(spec, arguments)

    assert directory is None
    assert document == arguments
    assert document is not arguments
