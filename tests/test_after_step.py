"""``wiring.invoke`` runs the after-step after any operation (slices 242 D7, 262 D10).

The operations themselves are replaced by recorders, so what is checked is the one
place both doors run the after-step: after which operations, through which door, and
that the operation's result comes back unchanged.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import anyio
import pytest
import yaml
from mcp_server.presence_rig import idle_presence
from operations.pause_support import FakeChild, SpawnRecorder
from store.message_support import send_request
from store.question_support import (
    MEMBER_ID,
    OTHER_MEMBER_ID,
    insert_held_row,
    seed_members,
)
from user_configs import example_config_text

from amoeba import wiring, wiring_steps
from amoeba.config.home import StateLayout, config_path, state_layout
from amoeba.config.user_config import ConfigError, UserConfig
from amoeba.mcp import server
from amoeba.operations.answer import AnswerOutcome, AnswerResult
from amoeba.operations.deps import Deps
from amoeba.operations.message_models import ReplyOutcome
from amoeba.operations.message_results import ReplyResult
from amoeba.operations.names import Door, OperationName
from amoeba.operations.prune_models import PruneReport
from amoeba.store.errors import StoreBusyError
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.models import QuestionKey
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from amoeba.wiring_door import take_work_keys
from amoeba.wiring_steps import LastReply

SCRIPT = Path("/installed/bin/amoeba")
HELD = QuestionKey("held-run", "2026-11-10T11:00:00+00:00")
REQUEST_ID = "ended-request"
#: Where each operation is looked up when ``invoke`` dispatches it: every served
#: operation goes through the one placement (261 D5, D12).
PLACEMENT = {
    name: (wiring, "place_served")
    for name in (
        OperationName.ADD,
        OperationName.RM,
        OperationName.LIST,
        OperationName.STATUS,
        OperationName.SEND,
        OperationName.REPLY,
        OperationName.CANCEL,
        OperationName.INBOX,
    )
}


@pytest.fixture(autouse=True)
def _config() -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> Iterator[SpawnRecorder]:
    """A held row whose request is done, and deps whose spawns are recorded."""
    recorder = SpawnRecorder([FakeChild(0)])
    with wiring.open_store(state_layout()) as store:
        seed_members(store)
        with store.write() as transaction:
            send_request(
                transaction,
                REQUEST_ID,
                from_member=MEMBER_ID,
                to_member=OTHER_MEMBER_ID,
            )
            message = get_message(transaction, REQUEST_ID)
            assert message is not None
            change_state(
                transaction, message, RequestState.DONE, DeliveryEvent.DONE,
                OTHER_MEMBER_ID, message.created_at, StateFields(result="done"),
            )  # fmt: skip
            insert_held_row(transaction, HELD, request_id=REQUEST_ID)
    real_deps = wiring.default_deps

    def recording_deps(layout: StateLayout) -> Deps:
        return replace(real_deps(layout), spawn=recorder, amoeba_script=lambda: SCRIPT)

    monkeypatch.setattr(wiring, "default_deps", recording_deps)
    yield recorder


def _replaced(monkeypatch: pytest.MonkeyPatch, name: OperationName) -> object:
    """Replace ``name``'s operation with one that returns a fixed result."""
    result = _reply_result()
    module, attribute = PLACEMENT[name]

    def fixed(*arguments: object, **_keywords: object) -> ReplyResult:
        # The placement's last argument is the config loader; the real operation
        # loads the config once, and a test of the start's own load counts on that.
        load = arguments[-1]
        assert callable(load)
        load()
        return result

    monkeypatch.setattr(module, attribute, fixed)
    return result


def _reply_result() -> ReplyResult:
    return ReplyResult(
        outcome=ReplyOutcome.APPLIED, notice="n", rejection=None, request=None,
        problems=(),
    )  # fmt: skip


@pytest.mark.parametrize("name", sorted(PLACEMENT), ids=lambda name: name.value)
def test_every_operation_is_followed_by_the_after_step_through_the_cli_door(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    spawned: SpawnRecorder,
    name: OperationName,
) -> None:
    expected = _replaced(monkeypatch, name)

    result = wiring.invoke(name, {}, tmp_path, Door.CLI)

    assert result is expected
    (call,) = spawned.calls
    assert call.argv == (str(SCRIPT), "handle-pause", "--json", "--", HELD.run_id)


def test_the_result_is_the_same_with_no_held_question(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = _replaced(monkeypatch, OperationName.REPLY)

    assert wiring.invoke(OperationName.REPLY, {}, tmp_path, Door.CLI) is expected


@pytest.mark.parametrize(
    "name", [OperationName.REPLY, OperationName.CANCEL], ids=lambda n: n.value
)
def test_the_mcp_door_starts_the_ended_held_question_too(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    spawned: SpawnRecorder,
    name: OperationName,
) -> None:
    _replaced(monkeypatch, name)
    arguments = {"id": REQUEST_ID, "directory": str(tmp_path)}
    if name is OperationName.REPLY:
        arguments["action"] = "accept"

    async def call() -> bool:
        result = await server.call_tool(name.value, arguments, idle_presence())
        return bool(result.is_error)

    assert anyio.run(call) is False
    (started,) = spawned.calls
    assert started.argv[-1] == HELD.run_id


def test_an_operation_that_raises_still_starts_the_ended_held_question(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spawned: SpawnRecorder
) -> None:
    def fails(*_arguments: object, **_keywords: object) -> ReplyResult:
        raise StoreBusyError("the store stayed busy after the reply committed")

    monkeypatch.setattr(wiring, "place_served", fails)

    with pytest.raises(StoreBusyError, match="after the reply committed"):
        wiring.invoke(OperationName.REPLY, {}, tmp_path, Door.CLI)

    (started,) = spawned.calls
    assert started.argv[-1] == HELD.run_id


def test_a_config_that_cannot_load_for_the_start_is_logged_not_raised(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    spawned: SpawnRecorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    expected = _replaced(monkeypatch, OperationName.REPLY)

    real_load = wiring.load_config
    loads: list[int] = []

    def broken_after_the_operation() -> UserConfig:
        """The operation's own load works; the start's, after it, fails."""
        loads.append(1)
        if len(loads) > 1:
            raise ConfigError("config.yaml went missing after the reply")
        return real_load()

    monkeypatch.setattr(wiring, "load_config", broken_after_the_operation)

    assert wiring.invoke(OperationName.REPLY, {}, tmp_path, Door.CLI) is expected
    assert spawned.calls == []
    assert "the after-step stopped" in caplog.text
    assert "Traceback" not in caplog.text


def test_an_mcp_answer_runs_no_after_step(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spawned: SpawnRecorder
) -> None:
    result = AnswerResult(AnswerOutcome.RECORDED)

    def recorded(*_arguments: object, **_keywords: object) -> AnswerResult:
        return result

    monkeypatch.setattr(wiring, "answer", recorded)

    assert wiring.invoke(OperationName.ANSWER, {}, tmp_path, Door.MCP) is result
    assert spawned.calls == []

    # The same answer through the CLI door is followed by it.
    wiring.invoke(OperationName.ANSWER, {}, tmp_path, Door.CLI)
    (started,) = spawned.calls
    assert started.argv[-1] == HELD.run_id


def _old_log(path: Path, days: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("log", encoding="utf-8")
    moment = time.time() - days * 24 * 3600
    os.utime(path, (moment, moment))
    return path


def test_a_machine_that_only_sends_and_reads_prunes_wake_and_resume_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = UserConfig.model_validate(yaml.safe_load(example_config_text()))
    logs = state_layout().logs_dir
    old_wake = _old_log(logs / "wake" / "w-old.stdout.log", config.prune_after_days + 5)
    old_resume = _old_log(
        logs / "resume" / "no-open-run" / "1.attempt", config.prune_after_days + 5
    )
    young = _old_log(logs / "wake" / "w-young.stdout.log", 1)
    _replaced(monkeypatch, OperationName.INBOX)

    wiring.invoke(OperationName.INBOX, {}, tmp_path, Door.CLI)

    assert not old_wake.exists()
    assert not old_resume.exists()
    assert young.exists()


def test_a_prune_problem_after_send_is_a_log_line_and_not_in_the_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    expected = _replaced(monkeypatch, OperationName.SEND)
    real_deps = wiring.default_deps

    def prune_problem(open_runs: object, *, now: datetime) -> PruneReport:  # noqa: ARG001
        return PruneReport(removed=0, problems=("prune: cannot remove a file",))

    def deps_with_problem(layout: StateLayout) -> Deps:
        return replace(real_deps(layout), prune=prune_problem)  # type: ignore[arg-type]

    monkeypatch.setattr(wiring, "default_deps", deps_with_problem)

    result = wiring.invoke(OperationName.SEND, {}, tmp_path, Door.CLI)

    assert result is expected
    assert "prune: cannot remove a file" in caplog.text


def test_a_door_replys_work_keys_go_to_the_holder_and_out_of_the_result() -> None:
    result: dict[str, object] = {"read": 2, "work": True, "work_problem": "bad yaml"}
    last = LastReply()

    take_work_keys(result, last)

    assert result == {"read": 2}
    assert last.work is True
    assert last.problem == "bad yaml"


def test_a_reply_with_no_work_keys_leaves_the_holder_empty() -> None:
    result: dict[str, object] = {"read": 2}
    last = LastReply()

    take_work_keys(result, last)

    assert result == {"read": 2}
    assert last == LastReply()


@pytest.mark.parametrize(
    ("name", "document", "prunes"),
    [
        (OperationName.STATUS, {}, False),
        (OperationName.LIST, {}, False),
        (OperationName.LIST, {"subject": "members"}, True),
        (OperationName.DECISIONS, {}, True),
    ],
)
def test_the_after_step_prunes_unless_the_operation_pruned_in_its_placement(
    monkeypatch: pytest.MonkeyPatch, name: OperationName, document: object, prunes: bool
) -> None:
    seen: list[bool] = []

    def record(*_args: object, prunes: bool) -> None:
        seen.append(prunes)

    monkeypatch.setattr(wiring_steps, "after_call", record)

    wiring_steps.after_operation(
        name, document, Door.CLI, None, LastReply(), lambda: _unused_deps()
    )

    assert seen == [prunes]


def _unused_deps() -> Deps:
    raise AssertionError("the recorder reads no deps")
