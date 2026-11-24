"""The hub serves the steps and puts the work flag in every done reply (262 D3, D10)."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from store.decision_support import CORE, FIRST, automatic_answer
from store.seed import mark_wake_wanted

from amoeba.config.user_config import ConfigError, UserConfig
from amoeba.store.store import Store
from amoeba.wire.protocol import (
    HEADER_DOOR_VERSION,
    WORK_PROBLEM_REPLY_KEY,
    WORK_REPLY_KEY,
    DoneReply,
    RefusalCode,
    RefusedReply,
)
from hub.call_support import ALPHA_TOKEN, HubRig, build_rig, result_of

LOGS = {"logs_dir": "/machine/logs"}


@pytest.fixture
def rig(tmp_path: Path) -> HubRig:
    return build_rig(tmp_path)


@contextmanager
def _as_alpha(rig: HubRig) -> Generator[Store]:
    with rig.open_store() as store:
        alpha = rig.machine(ALPHA_TOKEN)
        assert alpha is not None
        store.act_as(alpha)
        yield store


def _done(rig: HubRig, name: str, document: object, call_id: str) -> DoneReply:
    parsed = result_of(rig.call(name, document, call_id=call_id))
    assert isinstance(parsed, DoneReply), parsed
    return parsed


def _refused(rig: HubRig, name: str, document: object) -> RefusedReply:
    parsed = result_of(rig.call(name, document))
    assert isinstance(parsed, RefusedReply), parsed
    return parsed


def test_a_name_in_no_list_is_not_served(rig: HubRig) -> None:
    assert _refused(rig, "no_such_step", {}).code is RefusalCode.NOT_SERVED


def test_a_step_document_that_does_not_fit_is_malformed(rig: HubRig) -> None:
    refused = _refused(rig, "claim_work", {"logs_dir": 3, "extra": True})

    assert refused.code is RefusalCode.MALFORMED_CALL
    assert "claim_work" in refused.message


def test_a_read_step_is_served_with_the_flag(rig: HubRig) -> None:
    done = _done(rig, "open_runs", {}, "c1")

    assert done.result[WORK_REPLY_KEY] is False
    assert "run_ids" in done.result


def test_a_writing_step_repeated_with_its_call_id_applies_once_and_keeps_its_reply(
    rig: HubRig,
) -> None:
    with _as_alpha(rig) as store:
        automatic_answer(store, FIRST, CORE, 1)

    first = _done(rig, "claim_work", LOGS, "same")
    again = _done(rig, "claim_work", LOGS, "same")

    items = first.result["items"]
    assert isinstance(items, list) and len(items) == 1  # pyright: ignore[reportUnknownArgumentType]
    assert again.result["items"] == items
    assert rig.rows("SELECT resume_start_count FROM answers") == [(1,)]


def test_a_done_reply_carries_the_flag_and_a_repeat_gets_a_fresh_one(
    rig: HubRig,
) -> None:
    before = _done(rig, "mark_read", {"through": 0}, "mark")
    with _as_alpha(rig) as store:
        automatic_answer(store, FIRST, CORE, 1)

    repeat = _done(rig, "mark_read", {"through": 0}, "mark")

    assert before.result[WORK_REPLY_KEY] is False
    assert repeat.result[WORK_REPLY_KEY] is True
    stored = rig.rows("SELECT reply FROM call_results")
    assert len(stored) == 1
    assert WORK_REPLY_KEY not in str(stored[0][0])


def test_a_refused_reply_carries_no_flag(rig: HubRig) -> None:
    refused = rig.call("claim_work", {"logs_dir": 3})

    assert b'"work"' not in refused.body


def _broken() -> UserConfig:
    raise ConfigError("config.yaml: answering_wait_seconds: not a number")


@pytest.mark.parametrize(
    ("name", "document"),
    [
        ("mark_read", {"through": 0}),
        (
            "wake_finish",
            {
                "wake_id": "no-such-wake",
                "outcome": "exited",
                "exit_code": 0,
                "detail": None,
            },
        ),
    ],
)
def test_with_a_broken_config_a_call_needing_none_succeeds_with_the_problem(
    rig: HubRig, name: str, document: dict[str, object]
) -> None:
    rig.config = _broken

    done = _done(rig, name, document, "c1")

    assert WORK_REPLY_KEY not in done.result
    problem = done.result[WORK_PROBLEM_REPLY_KEY]
    assert isinstance(problem, str) and "answering_wait_seconds" in problem


def test_with_a_broken_config_a_step_needing_it_is_a_hub_error(rig: HubRig) -> None:
    rig.config = _broken

    refused = _refused(rig, "claim_work", LOGS)

    assert refused.code is RefusalCode.HUB_ERROR
    assert "answering_wait_seconds" in refused.message


def test_a_client_at_door_version_1_sending_is_refused_and_writes_nothing(
    rig: HubRig,
) -> None:
    send = {"id": "ask", "to": "lint-name", "subject": "s", "body": "b"}

    reply = rig.call(
        "send",
        send,
        headers={HEADER_DOOR_VERSION: "1"},
        extra={"here": {"project_id": CORE}, "logs_dir": "/machine/logs"},
    )

    refused = result_of(reply)
    assert isinstance(refused, RefusedReply)
    assert refused.code is RefusalCode.DOOR_VERSION
    assert rig.rows("SELECT COUNT(*) FROM messages") == [(0,)]
    assert rig.rows("SELECT COUNT(*) FROM wakes") == [(0,)]


def test_a_kept_reply_gets_its_flag_acting_as_the_caller_when_a_wake_is_due(
    rig: HubRig,
) -> None:
    """The flag's wake check reads the acting machine; a repeat that returns a kept
    result must act as the caller too."""
    first = _done(rig, "mark_read", {"through": 0}, "mark")
    with _as_alpha(rig) as store, store.write() as transaction:
        transaction.execute(
            "UPDATE checkouts SET wake_command = 'wake-agent' WHERE member_id = ?",
            (CORE,),
        )
        mark_wake_wanted(transaction, CORE, rig.clock())

    repeat = _done(rig, "mark_read", {"through": 0}, "mark")

    assert first.result[WORK_REPLY_KEY] is False
    assert repeat.result[WORK_REPLY_KEY] is True
