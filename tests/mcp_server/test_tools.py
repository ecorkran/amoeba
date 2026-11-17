"""The tool table: names, modes, advice, schemas and argument preparation
(slice 226, D2, D5, D12).

This directory is not named ``mcp``: a test package of that name would shadow the
SDK when pytest puts ``tests/`` on the import path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amoeba.cli.parser import build_parser
from amoeba.cli.wake_command import CLI_ONLY_COMMANDS
from amoeba.mcp.message_tools import SEND_ADVICE, STATE_CHANGE_ADVICE
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
from amoeba.operations.message_models import MAX_BODY_LENGTH, MAX_ID_LENGTH
from amoeba.operations.names import OperationName
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.wiring_messages import worst_case_seconds

MESSAGE_TOOL_NAMES = (
    OperationName.SEND,
    OperationName.INBOX,
    OperationName.REPLY,
    OperationName.CANCEL,
)
DIRECTORY_TOOLS = {
    OperationName.ADD,
    OperationName.RM,
    OperationName.LIST,
    OperationName.STATUS,
    OperationName.HANDLE_PAUSE,
    OperationName.REPORT_RELEASE,
    OperationName.CHANGES,
    *MESSAGE_TOOL_NAMES,
}
READ_TOOLS = {
    OperationName.STATUS,
    OperationName.DECISIONS,
    OperationName.LIST,
    OperationName.CHANGES,
    OperationName.INBOX,
}
#: The message tools that write: their advice points at ``inbox``.
MESSAGE_WRITE_TOOLS = {OperationName.SEND, OperationName.REPLY, OperationName.CANCEL}
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
    assert {
        name.cli_name for name in OperationName
    } == _subcommands() - CLI_ALIASES - CLI_ONLY_COMMANDS


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
            if tool.name is OperationName.SEND:
                expected = SEND_ADVICE
            elif tool.name in MESSAGE_WRITE_TOOLS:
                expected = STATE_CHANGE_ADVICE
            else:
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


def test_the_changes_tool_tells_the_agent_report_text_is_quoted_data() -> None:
    assert QUOTED_DATA_NOTICE in _spec(OperationName.CHANGES).description


@pytest.mark.parametrize(
    "name",
    [OperationName.LIST, OperationName.STATUS, *MESSAGE_TOOL_NAMES],
    ids=lambda name: name.value,
)
def test_every_tool_that_shows_message_text_carries_the_notice(
    name: OperationName,
) -> None:
    assert QUOTED_DATA_NOTICE in _spec(name).description


@pytest.mark.parametrize("name", sorted(MESSAGE_WRITE_TOOLS), ids=lambda n: n.value)
def test_a_write_tool_says_a_rejection_after_a_timeout_means_the_first_call_landed(
    name: OperationName,
) -> None:
    description = _spec(name).description

    assert f"If `{name.value}` is rejected after a timeout" in description
    assert "`inbox` shows the state" in description


WORST_CASES = {
    OperationName.SEND: worst_case_seconds(OperationName.SEND),
    OperationName.INBOX: worst_case_seconds(OperationName.INBOX),
    OperationName.REPLY: worst_case_seconds(OperationName.REPLY),
    OperationName.CANCEL: worst_case_seconds(OperationName.CANCEL),
}


@pytest.mark.parametrize("name", MESSAGE_TOOL_NAMES, ids=lambda n: n.value)
def test_a_message_tool_names_its_worst_case_wait(name: OperationName) -> None:
    assert f"up to {WORST_CASES[name]:g} s" in _spec(name).description


def test_the_send_tool_states_the_id_and_text_limits() -> None:
    description = _spec(OperationName.SEND).description

    assert str(MAX_ID_LENGTH) in description
    assert str(MAX_BODY_LENGTH) in description


def test_the_message_tools_take_the_request_models_plus_a_directory() -> None:
    for name in MESSAGE_TOOL_NAMES:
        spec = _spec(name)
        schema = input_schema(spec)
        model_properties = spec.request_model.model_json_schema()["properties"]
        assert set(schema["properties"]) == {*model_properties, "directory"}
        assert "directory" in schema["required"]


def test_only_the_send_advice_calls_a_repeat_safe() -> None:
    assert "repeated `send` with the same `id` is safe" in SEND_ADVICE
    assert "`send`" not in STATE_CHANGE_ADVICE
    assert "rejected naming the state" in STATE_CHANGE_ADVICE


def test_the_send_tool_takes_kind_and_to_program_and_still_needs_neither() -> None:
    schema = input_schema(_spec(OperationName.SEND))

    assert {"kind", "to_program"} <= set(schema["properties"])
    assert "kind" not in schema["required"]
    assert "to_program" not in schema["required"]
    assert "to" not in schema["required"]


def test_the_send_and_inbox_descriptions_say_a_note_needs_no_reply() -> None:
    send = _spec(OperationName.SEND).description
    inbox = _spec(OperationName.INBOX).description

    assert "`kind` `note`" in send and "needs no reply" in send
    assert "`to_program`" in send
    assert "`notes`" in inbox and "needs no reply" in inbox


def test_the_add_schema_has_no_wake_command_anywhere() -> None:
    """The wake command is the PM's CLI setting (244 D1): no field of the published
    schema, at the top or in a bulk member, offers it."""
    schema = input_schema(_spec(OperationName.ADD))

    assert "wake_command" not in json.dumps(schema)
