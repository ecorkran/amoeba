"""``run_in_process``: the same call as the CLI, off the loop, under a deadline
(slice 226, D4, D12)."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

import anyio
import pytest
import yaml
from user_configs import example_config_text
from wiring_support import is_closed, record_opened_stores

from amoeba import wiring
from amoeba.cli import main as cli
from amoeba.config.home import config_path
from amoeba.mcp import in_process
from amoeba.mcp.in_process import CallTimedOut, run_in_process
from amoeba.mcp.tools import (
    READ_ADVICE,
    TOOLS,
    WRITE_ADVICE,
    RunMode,
    ToolSpec,
    prepare_arguments,
)
from amoeba.operations.mark_read import MarkReadOutcome, MarkReadResult
from amoeba.operations.names import Door, OperationName
from amoeba.store.store import Store
from amoeba.upstream.squadron.errors import SquadronError

IN_PROCESS_TOOLS = [tool for tool in TOOLS if tool.mode is RunMode.IN_PROCESS]
REQUEST_FILE = "<request file>"
#: Each in-process tool: its CLI arguments and the same input as MCP arguments.
CASES: dict[OperationName, tuple[list[str], dict[str, object]]] = {
    OperationName.SET_UP: (["set_up", "--file", REQUEST_FILE], {"program": "trial"}),
    OperationName.STATUS: (["status", "--program", "p"], {"program": "p"}),
    OperationName.DECISIONS: (
        ["decisions", "--since", "2026-11-10T00:00:00+00:00", "--program", "p"],
        {"since": "2026-11-10T00:00:00+00:00", "program": "p"},
    ),
    OperationName.MARK_READ: (["mark_read", "--through", "3"], {"through": 3}),
    OperationName.ANSWER: (
        ["answer", "r1", "--text", "yes"],
        {"run_id": "r1", "text": "yes"},
    ),
    OperationName.DISMISS: (
        ["dismiss", "r1", "--reason", "why"],
        {"run_id": "r1", "reason": "why"},
    ),
    OperationName.RETRACT: (
        ["retract", "7", "--reason", "why"],
        {"answer_seq": 7, "reason": "why"},
    ),
}
STUB_RESULT = MarkReadResult(outcome=MarkReadOutcome.UNCHANGED, previous=0, current=0)
WAIT_SECONDS = 10


def _spec(name: OperationName) -> ToolSpec:
    (spec,) = (tool for tool in TOOLS if tool.name is name)
    return spec


@pytest.fixture(autouse=True)
def _config() -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")


def _call(
    name: OperationName, arguments: dict[str, object], directory: Path
) -> dict[str, object]:
    """What the MCP door returns for ``arguments``, run to completion."""
    spec = _spec(name)
    raw = (
        {**arguments, "directory": str(directory)}
        if spec.takes_directory
        else arguments
    )
    document, parsed_directory = prepare_arguments(spec, raw)

    async def run() -> dict[str, object]:
        return await run_in_process(spec, document, parsed_directory)

    return anyio.run(run)


@pytest.mark.parametrize("name", list(CASES), ids=lambda name: name.value)
def test_both_doors_reach_invoke_with_the_same_call(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    name: OperationName,
) -> None:
    request = tmp_path / "request.yaml"
    request.write_text("program: trial\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[OperationName, object, Path | None, Door]] = []

    def recorder(
        name: OperationName, document: object, directory: Path | None, door: Door
    ) -> MarkReadResult:
        calls.append((name, document, directory, door))
        return STUB_RESULT

    monkeypatch.setattr(cli, "invoke", recorder)
    monkeypatch.setattr(wiring, "invoke", recorder)
    argv, arguments = CASES[name]

    cli.main([str(request) if part == REQUEST_FILE else part for part in argv])
    printed = json.loads(capsys.readouterr().out)
    returned = _call(name, arguments, Path.cwd())

    (by_cli, by_mcp) = calls
    assert by_cli[0] is by_mcp[0] is name
    assert by_cli[1] == by_mcp[1]
    if _spec(name).takes_directory:
        assert by_cli[2] == by_mcp[2] == Path.cwd()
    assert (by_cli[3], by_mcp[3]) == (Door.CLI, Door.MCP)
    assert returned == printed


def test_the_real_invoke_gives_the_same_json_through_both_doors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    cli.main(["mark_read", "--through", "0"])
    printed = json.loads(capsys.readouterr().out)
    returned = _call(OperationName.MARK_READ, {"through": 0}, tmp_path)

    assert returned == printed
    assert returned["outcome"] == "unchanged"


def test_a_malformed_set_up_is_a_rejected_result_on_both_doors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    request = tmp_path / "request.yaml"
    request.write_text("bogus: 1\n", encoding="utf-8")

    code = cli.main(["set_up", "--file", str(request)])
    printed = json.loads(capsys.readouterr().out)
    returned = _call(OperationName.SET_UP, {"bogus": 1}, tmp_path)

    assert code == cli.EXIT_REJECTED
    assert returned == printed
    assert returned["outcome"] == "rejected"


def _blocking(release: threading.Event) -> Callable[..., MarkReadResult]:
    """A stand-in for ``invoke`` that waits for ``release`` when asked to block."""

    def invoke(
        name: OperationName, document: object, directory: Path | None, door: Door
    ) -> MarkReadResult:
        if isinstance(document, dict) and document.get("block"):  # pyright: ignore[reportUnknownMemberType]
            assert release.wait(WAIT_SECONDS), "the test never released the worker"
        return STUB_RESULT

    return invoke


def test_a_blocked_tool_does_not_stop_a_second_call_completing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    monkeypatch.setattr(wiring, "invoke", _blocking(release))
    spec = _spec(OperationName.MARK_READ)

    seconds: list[dict[str, object]] = []

    async def scenario() -> None:
        async with anyio.create_task_group() as group:
            group.start_soon(run_in_process, spec, {"block": True}, None)
            await anyio.sleep(0.1)
            with anyio.fail_after(WAIT_SECONDS):
                seconds.append(await run_in_process(spec, {"through": 0}, None))
            release.set()

    try:
        anyio.run(scenario)
    finally:
        release.set()
    assert [second["outcome"] for second in seconds] == ["unchanged"]


def test_a_call_past_the_deadline_times_out_and_a_following_call_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    monkeypatch.setattr(wiring, "invoke", _blocking(release))
    monkeypatch.setattr(in_process, "MCP_CALL_DEADLINE_SECONDS", 0.2)
    spec = _spec(OperationName.MARK_READ)

    async def scenario() -> float:
        started = time.monotonic()
        with pytest.raises(CallTimedOut):
            await run_in_process(spec, {"block": True}, None)
        elapsed = time.monotonic() - started
        assert (await run_in_process(spec, {"through": 0}, None))["outcome"]
        return elapsed

    try:
        elapsed = anyio.run(scenario)
    finally:
        release.set()
    assert 0.15 <= elapsed < 5


def _wait_until(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        assert time.monotonic() < deadline, "the worker thread never finished"
        time.sleep(0.01)


def test_the_abandoned_worker_closes_its_store_when_it_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    opened = record_opened_stores(monkeypatch)

    def slow_mark_read(store: Store, document: object) -> MarkReadResult:
        assert release.wait(WAIT_SECONDS), "the test never released the worker"
        return STUB_RESULT

    monkeypatch.setattr(wiring, "mark_read", slow_mark_read)
    monkeypatch.setattr(in_process, "MCP_CALL_DEADLINE_SECONDS", 0.2)

    async def scenario() -> None:
        with pytest.raises(CallTimedOut):
            await run_in_process(_spec(OperationName.MARK_READ), {"through": 0}, None)

    try:
        anyio.run(scenario)
        (store,) = opened
        assert not is_closed(store)
    finally:
        release.set()
    _wait_until(lambda: is_closed(store))


def test_the_store_is_closed_after_a_normal_call_and_after_one_that_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = record_opened_stores(monkeypatch)
    spec = _spec(OperationName.MARK_READ)

    async def normal() -> None:
        await run_in_process(spec, {"through": 0}, None)

    anyio.run(normal)
    assert [is_closed(store) for store in opened] == [True]

    def raising(store: Store, document: object) -> MarkReadResult:
        raise SquadronError("sq down")

    monkeypatch.setattr(wiring, "mark_read", raising)

    async def failing() -> None:
        with pytest.raises(SquadronError):
            await run_in_process(spec, {"through": 0}, None)

    anyio.run(failing)
    assert [is_closed(store) for store in opened] == [True, True]


@pytest.mark.parametrize("tool", IN_PROCESS_TOOLS, ids=lambda tool: tool.name.value)
def test_the_timed_out_text_carries_that_tools_advice(
    monkeypatch: pytest.MonkeyPatch, tool: ToolSpec
) -> None:
    release = threading.Event()
    monkeypatch.setattr(wiring, "invoke", _blocking(release))
    monkeypatch.setattr(in_process, "MCP_CALL_DEADLINE_SECONDS", 0.05)

    # A 0.05 s deadline is below any real ``answer`` bound; this test is about the
    # text of a timeout, so the per-call config check is set aside.
    def no_check(config: object, deadline: float) -> None:
        return None

    monkeypatch.setattr(wiring, "check_deadline", no_check)
    advice = (
        READ_ADVICE
        if tool.name in {OperationName.STATUS, OperationName.DECISIONS}
        else WRITE_ADVICE
    )

    async def scenario() -> None:
        await run_in_process(tool, {"block": True}, Path("/tmp"))

    try:
        with pytest.raises(CallTimedOut) as raised:
            anyio.run(scenario)
    finally:
        release.set()
    assert str(raised.value) == (
        f"{tool.name.value} did not finish within 0.05 s; {advice}"
    )


def _raise_resume_wait(seconds: float) -> None:
    """Edit the running world's config, as a person could while a server runs."""
    path = config_path()
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["resume_wait_seconds"] = seconds
    path.write_text(yaml.safe_dump(config), encoding="utf-8")


def test_an_answer_is_refused_before_it_acts_when_the_config_outgrew_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[OperationName] = []

    def recorder(
        name: OperationName, document: object, directory: Path | None, door: Door
    ) -> MarkReadResult:
        calls.append(name)
        return STUB_RESULT

    monkeypatch.setattr(wiring, "invoke", recorder)
    _raise_resume_wait(in_process.MCP_CALL_DEADLINE_SECONDS)

    async def scenario() -> None:
        await run_in_process(_spec(OperationName.ANSWER), {"run_id": "r"}, None)

    with pytest.raises(wiring.DeadlineError, match="resume_wait_seconds"):
        anyio.run(scenario)

    assert calls == []


def test_only_answer_is_held_to_the_answer_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def stub_invoke(*_arguments: object) -> MarkReadResult:
        return STUB_RESULT

    monkeypatch.setattr(wiring, "invoke", stub_invoke)
    _raise_resume_wait(in_process.MCP_CALL_DEADLINE_SECONDS)

    async def scenario() -> dict[str, object]:
        return await run_in_process(
            _spec(OperationName.MARK_READ), {"through": 0}, None
        )

    assert anyio.run(scenario)["outcome"] == "unchanged"


def test_an_exception_raised_after_the_deadline_is_logged_at_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    release = threading.Event()

    def failing_late(
        name: OperationName, document: object, directory: Path | None, door: Door
    ) -> MarkReadResult:
        assert release.wait(WAIT_SECONDS), "the test never released the worker"
        raise SquadronError("sq went away")

    monkeypatch.setattr(wiring, "invoke", failing_late)
    monkeypatch.setattr(in_process, "MCP_CALL_DEADLINE_SECONDS", 0.05)

    async def scenario() -> None:
        with pytest.raises(CallTimedOut):
            await run_in_process(_spec(OperationName.MARK_READ), {"through": 0}, None)

    with caplog.at_level(logging.ERROR, logger=in_process.__name__):
        try:
            anyio.run(scenario)
        finally:
            release.set()
        _wait_until(lambda: any(r.levelno == logging.ERROR for r in caplog.records))

    (record,) = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.name == in_process.__name__
    assert record.exc_info is not None
    assert "sq went away" in str(record.exc_info[1])
