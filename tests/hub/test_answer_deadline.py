"""The hub part of ``answer`` against the MCP call deadline (slice 263, D9)."""

from __future__ import annotations

from pathlib import Path

import pytest
from store.decision_support import CORE, FIRST
from store.question_support import waiting_question
from user_configs import user_config

from amoeba import wiring
from amoeba.operations.errors import OPERATION_ERRORS, DeadlineError
from amoeba.operations.steps.limits import resume_claim_seconds
from amoeba.store.questions import insert_question
from amoeba.wire.protocol import DoneReply, RefusalCode, RefusedReply
from amoeba.wire.times import MCP_CALL_DEADLINE_SECONDS
from hub.call_support import ALPHA_TOKEN, NOW, HubRig, build_rig, result_of

#: The largest ``resume_wait_seconds`` that passes the hub's check: the deadline less
#: the resume claim time's fixed part (216.5 - 60 for the example config).
LARGEST = MCP_CALL_DEADLINE_SECONDS - (resume_claim_seconds(user_config()) - 60)


@pytest.fixture
def rig(tmp_path: Path) -> HubRig:
    built = build_rig(tmp_path)
    with built.open_store() as store:
        machine = built.machine(ALPHA_TOKEN)
        assert machine is not None
        store.act_as(machine)
        with store.write() as transaction:
            insert_question(
                transaction, waiting_question(FIRST, member_id=CORE), now=NOW
            )
    return built


def _answer(rig: HubRig, wait: float, via: str) -> DoneReply | RefusedReply:
    config = user_config().model_copy(update={"resume_wait_seconds": wait})
    rig.config = lambda: config
    reply = result_of(
        rig.call(
            "answer",
            {"run_id": FIRST.run_id, "text": "300 lines"},
            extra={"via": via},
        )
    )
    assert isinstance(reply, DoneReply | RefusedReply)
    return reply


def test_the_largest_passing_wait_is_143_5() -> None:
    assert LARGEST == 143.5


@pytest.mark.parametrize("wait", [LARGEST, LARGEST + 50])
def test_a_wait_the_deadline_cannot_cover_is_refused_naming_the_key_and_the_largest(
    rig: HubRig, wait: float
) -> None:
    refused = _answer(rig, wait, "mcp")

    assert isinstance(refused, RefusedReply)
    assert refused.code is RefusalCode.HUB_ERROR
    assert "DeadlineError" in refused.message
    assert "resume_wait_seconds" in refused.message
    assert "hub's config.yaml" in refused.message
    assert f"below {LARGEST:g}" in refused.message
    assert rig.rows("SELECT COUNT(*) FROM answers") == [(0,)]


def test_the_example_config_records_and_hands_over_the_resume(rig: HubRig) -> None:
    done = _answer(rig, 60, "mcp")

    assert isinstance(done, DoneReply)
    assert rig.rows("SELECT COUNT(*) FROM answers") == [(1,)]
    assert rig.rows("SELECT resume_claim_id IS NOT NULL FROM answers") == [(1,)]


def test_the_same_answer_from_the_cli_is_not_checked(rig: HubRig) -> None:
    done = _answer(rig, LARGEST + 50, "cli")

    assert isinstance(done, DoneReply)
    assert rig.rows("SELECT COUNT(*) FROM answers") == [(1,)]


def test_the_local_check_is_unchanged_and_bounds_by_209_5() -> None:
    config = user_config().model_copy(update={"resume_wait_seconds": 209})
    wiring.check_deadline(config, MCP_CALL_DEADLINE_SECONDS)
    with pytest.raises(DeadlineError):
        wiring.check_deadline(
            config.model_copy(update={"resume_wait_seconds": 209.5}),
            MCP_CALL_DEADLINE_SECONDS,
        )


def test_deadline_error_is_one_class_the_hub_catches_as_an_operation_error() -> None:
    assert wiring.DeadlineError is DeadlineError
    assert DeadlineError in OPERATION_ERRORS
