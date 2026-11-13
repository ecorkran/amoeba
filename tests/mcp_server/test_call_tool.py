"""``call_tool``: results and the error rows of D7 (slice 226, task 5.1)."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import anyio
import mcp_types as types
import pytest

from amoeba import wiring
from amoeba.config.user_config import ConfigError
from amoeba.mcp import server
from amoeba.mcp.detached import (
    AmoebaScriptMissing,
    HandlePauseNotStarted,
    StartedCall,
)
from amoeba.mcp.in_process import CallTimedOut
from amoeba.mcp.tools import ToolSpec
from amoeba.operations.members import ContextForgeError
from amoeba.operations.names import OperationName
from amoeba.store.errors import StoreBusyError
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.wiring import DeadlineError

REJECTED_STYLE_RESULT: dict[str, object] = {"outcome": "rejected", "problems": ["x"]}
STARTED = StartedCall(
    operation=OperationName.HANDLE_PAUSE,
    pid=4242,
    cwd=Path("/tmp/repo"),
    started_at=datetime(2026, 11, 12, 12, 0, tzinfo=UTC),
    stdout_log=Path("/tmp/out.log"),
    stderr_log=Path("/tmp/err.log"),
)
HANDLE_PAUSE_ARGUMENTS: dict[str, object] = {"run_id": "r", "directory": "/tmp/repo"}


def _call(name: str, arguments: Mapping[str, object] | None) -> types.CallToolResult:
    async def run() -> types.CallToolResult:
        return await server.call_tool(name, arguments)

    return anyio.run(run)


def _text(result: types.CallToolResult) -> str:
    (block,) = result.content
    assert isinstance(block, types.TextContent)
    return block.text


class _InProcess:
    """A stand-in for ``run_in_process``: records calls, then returns or raises."""

    def __init__(
        self, *, result: dict[str, object] | None = None, error: Exception | None = None
    ) -> None:
        self.calls: list[tuple[OperationName, object, Path | None]] = []
        self._result = result
        self._error = error

    async def __call__(
        self, spec: ToolSpec, document: object, directory: Path | None
    ) -> dict[str, object]:
        self.calls.append((spec.name, document, directory))
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _Detached:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[object] = []
        self._error = error

    async def __call__(self, raw: Mapping[str, object] | None) -> StartedCall:
        self.calls.append(raw)
        if self._error is not None:
            raise self._error
        return STARTED


def test_a_rejected_style_result_is_a_normal_result_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        server, "run_in_process", _InProcess(result=REJECTED_STYLE_RESULT)
    )

    result = _call("mark_read", {"through": "x"})

    assert result.is_error is False
    assert result.structured_content == REJECTED_STYLE_RESULT


def test_structured_content_equals_the_parsed_text_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        server, "run_in_process", _InProcess(result=REJECTED_STYLE_RESULT)
    )

    result = _call("mark_read", {"through": 1})

    assert json.loads(_text(result)) == result.structured_content


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (CallTimedOut("status did not finish"), "TimedOut: status did not finish"),
        (DeadlineError("too long"), "DeadlineError: too long"),
        (SquadronError("sq down"), "SquadronError: sq down"),
        (ContextForgeError("cf down"), "ContextForgeError: cf down"),
        (ConfigError("bad key"), "ConfigError: bad key"),
        (StoreBusyError("busy"), "StoreBusyError: busy"),
    ],
    ids=lambda value: type(value).__name__ if isinstance(value, Exception) else None,
)
def test_each_in_process_error_row_is_an_error_with_the_stated_text(
    monkeypatch: pytest.MonkeyPatch, error: Exception, text: str
) -> None:
    monkeypatch.setattr(server, "run_in_process", _InProcess(error=error))

    result = _call("mark_read", {"through": 1})

    assert result.is_error is True
    assert _text(result) == text
    assert result.structured_content is None


def test_a_request_error_is_an_error_naming_the_field() -> None:
    result = _call("status", {"program": "x"})

    assert result.is_error is True
    assert _text(result).startswith("RequestError: directory")


def test_a_relative_handle_pause_directory_is_refused_by_the_one_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[object] = []

    def recording_start(*arguments: object) -> None:
        started.append(arguments)

    monkeypatch.setattr(wiring, "start_child", recording_start)

    result = _call("handle_pause", {"run_id": "r", "directory": "relative/path"})

    assert result.is_error is True
    assert _text(result).startswith("RequestError: directory")
    assert started == []


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (HandlePauseNotStarted("cannot start"), "HandlePauseNotStarted: cannot start"),
        (AmoebaScriptMissing("no script"), "AmoebaScriptMissing: no script"),
    ],
    ids=["launch-failure", "script-missing"],
)
def test_a_failed_detached_start_is_an_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception, text: str
) -> None:
    monkeypatch.setattr(server, "start_handle_pause", _Detached(error=error))

    result = _call("handle_pause", HANDLE_PAUSE_ARGUMENTS)

    assert result.is_error is True
    assert _text(result) == text


def test_an_unexpected_exception_is_logged_and_the_server_keeps_serving(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        server, "run_in_process", _InProcess(error=RuntimeError("a bug"))
    )

    with caplog.at_level(logging.ERROR, logger=server.__name__):
        failed = _call("mark_read", {"through": 1})
    monkeypatch.setattr(
        server, "run_in_process", _InProcess(result=REJECTED_STYLE_RESULT)
    )
    following = _call("mark_read", {"through": 1})

    assert failed.is_error is True
    assert _text(failed) == "internal error: a bug"
    (record,) = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.exc_info is not None and "a bug" in str(record.exc_info[1])
    assert following.is_error is False


def test_an_unknown_tool_name_is_an_error() -> None:
    result = _call("no_such_tool", {})

    assert result.is_error is True
    assert "no_such_tool" in _text(result)


def test_handle_pause_reaches_only_the_detached_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detached = _Detached()
    in_process = _InProcess(result=REJECTED_STYLE_RESULT)
    monkeypatch.setattr(server, "start_handle_pause", detached)
    monkeypatch.setattr(server, "run_in_process", in_process)

    result = _call("handle_pause", HANDLE_PAUSE_ARGUMENTS)

    assert detached.calls == [HANDLE_PAUSE_ARGUMENTS]
    assert in_process.calls == []
    assert result.is_error is False
    assert result.structured_content == STARTED.model_dump(mode="json")


def test_an_in_process_tool_reaches_only_the_in_process_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detached = _Detached()
    in_process = _InProcess(result=REJECTED_STYLE_RESULT)
    monkeypatch.setattr(server, "start_handle_pause", detached)
    monkeypatch.setattr(server, "run_in_process", in_process)

    _call("answer", {"run_id": "r", "text": "yes"})

    assert in_process.calls == [
        (OperationName.ANSWER, {"run_id": "r", "text": "yes"}, None)
    ]
    assert detached.calls == []
