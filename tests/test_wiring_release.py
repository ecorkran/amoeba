"""``wiring.invoke`` starts held questions after the operations that can end a request
(slice 242, D7, 6.5).

The operations themselves are replaced by recorders, so what is checked is the one
place both doors run ``start_after``: after which operations, through which door, and
that the operation's result comes back unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import anyio
import pytest
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

from amoeba import wiring
from amoeba.config.home import StateLayout, config_path, state_layout
from amoeba.config.user_config import ConfigError, UserConfig
from amoeba.mcp import server
from amoeba.operations.deps import Deps
from amoeba.operations.message_models import ReplyOutcome
from amoeba.operations.message_results import ReplyResult
from amoeba.operations.names import Door, OperationName
from amoeba.store.errors import StoreBusyError
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.models import QuestionKey
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from amoeba.wiring_release import START_AFTER_OPERATIONS

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


@pytest.mark.parametrize(
    "name", sorted(START_AFTER_OPERATIONS), ids=lambda name: name.value
)
def test_each_start_operation_starts_the_ended_held_question_through_the_cli_door(
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


def test_inbox_starts_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spawned: SpawnRecorder
) -> None:
    _replaced(monkeypatch, OperationName.INBOX)

    wiring.invoke(OperationName.INBOX, {}, tmp_path, Door.CLI)

    assert spawned.calls == []


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
    assert "held questions not started" in caplog.text
    assert "Traceback" not in caplog.text
