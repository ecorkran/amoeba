"""``handle-pause`` through the door when a step fails (262 D3, D10, D11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba import wiring_steps
from amoeba.answering.values import DeclineReason
from amoeba.client.errors import HubRefusedError, HubUnreachableError
from amoeba.operations.handle_pause import HandlePauseOutcome
from amoeba.operations.steps.limits import MAX_AUTOMATIC_STARTS, pause_claim_seconds
from amoeba.operations.steps.models import CLAIM_WORK
from amoeba.operations.steps.models_work import ClaimWorkRequest, HandlePauseItem
from amoeba.store.questions import get_question
from amoeba.store.vocabulary import QuestionState
from amoeba.wire.protocol import MAX_CALL_BYTES, RefusalCode
from amoeba.wiring_steps import DoorSteps, LastReply
from operations.handle_rig import (
    CHECK_YES,
    KEY,
    PAUSE,
    RUN,
    RUNNING_DOC,
    World,
    world,
)
from operations.pause_support import FakeClock
from operations.ways import DOOR


def _clock(w: World) -> FakeClock:
    clock = w.deps.clock
    assert isinstance(clock, FakeClock)
    return clock


def _handed_out(w: World) -> list[HandlePauseItem]:
    reply = DoorSteps(LastReply()).run(
        CLAIM_WORK, ClaimWorkRequest(logs_dir=str(w.deps.logs_dir))
    )
    return [i for i in reply.items if isinstance(i, HandlePauseItem)]


def _state(w: World) -> tuple[QuestionState, DeclineReason | None]:
    with w.store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    return record.state, record.waiting_reason


def test_a_hub_gone_after_the_insert_leaves_a_claim_the_next_call_starts_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = wiring_steps.call

    def hub_gone_at_settle(*args: object, **kwargs: object) -> dict[str, object]:
        if args[2] == "question_settle":
            raise HubUnreachableError("no reply from the hub")
        return real(*args, **kwargs)  # type: ignore[arg-type]

    polls = (PAUSE, PAUSE, PAUSE, RUNNING_DOC)
    with world(tmp_path, way=DOOR, paused_polls=polls) as w:
        monkeypatch.setattr(wiring_steps, "call", hub_gone_at_settle)
        with pytest.raises(HubUnreachableError):
            w.handle()
        monkeypatch.setattr(wiring_steps, "call", real)
        assert _state(w)[0] is QuestionState.CLAIMED

        _clock(w).advance(pause_claim_seconds(w.config))
        (item,) = _handed_out(w)
        assert item.run_id == RUN
        result = w.handle()

    assert result.outcome is HandlePauseOutcome.RESUMED, result


def test_a_settle_over_the_body_limit_is_refused_and_ends_starts_exhausted(
    tmp_path: Path,
) -> None:
    huge: dict[str, object] = {
        "kind": "answer",
        "answer": "x" * (MAX_CALL_BYTES // 2),
        "cited": ["P1"],
    }
    with world(tmp_path, way=DOOR, answer=huge, check=CHECK_YES) as w:
        with pytest.raises(HubRefusedError) as raised:
            w.handle()
        assert raised.value.code is RefusalCode.MALFORMED_CALL
        assert len(w.spawned.answering) == 1

        _clock(w).advance(pause_claim_seconds(w.config))
        handed = 0
        for _ in range(MAX_AUTOMATIC_STARTS):
            handed += len(_handed_out(w))
            _clock(w).advance(w.config.answering_wait_seconds)
        fourth = _handed_out(w)

        assert handed == MAX_AUTOMATIC_STARTS
        assert fourth == []
        assert _state(w) == (
            QuestionState.WAITING_ON_PM,
            DeclineReason.STARTS_EXHAUSTED,
        )
        assert len(w.spawned.answering) == 1
