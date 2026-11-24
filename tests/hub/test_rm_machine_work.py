"""``rm-machine`` closes what waits on the machine it removes (262 D13)."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from operations.wake_run_support import (
    WAKE_ID,
    process_is_gone,
    seed_claimed_wake,
    wait_until,
)
from operations.ways import DOOR, steps_on
from process_containment import contained_popen
from store.decision_support import CORE, FIRST, SECOND, THIRD, automatic_answer
from store.question_support import claimed_question, insert_held_row, waiting_question
from store.seed import mark_wake_wanted

from amoeba.client.errors import HubRefusedError
from amoeba.hub.admin import rm_machine
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.wake_run import run_wake
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.store.wakes import WakeLimits, claim_wake
from amoeba.wire.protocol import DoneReply
from amoeba.wiring_door import join
from hub.call_support import ALPHA_TOKEN, BETA_TOKEN, NOW, HubRig, build_rig, result_of
from hub.in_process_hub import InProcessHub
from hub.join_support import line_for

ON_BETA = QuestionKey("beta-run", "2026-11-10T12:00:00+00:00")


@contextmanager
def _acting(rig: HubRig, token: str) -> Generator[Store]:
    with rig.open_store() as store:
        machine = rig.machine(token)
        assert machine is not None
        store.act_as(machine)
        yield store


def _seed(rig: HubRig) -> None:
    with _acting(rig, ALPHA_TOKEN) as store:
        with store.write() as transaction:
            insert_question(
                transaction, claimed_question(FIRST, member_id=CORE), now=NOW
            )
            insert_held_row(transaction, THIRD, member_id=CORE, now=NOW)
            transaction.execute(
                "UPDATE checkouts SET wake_command = 'wake-agent' WHERE member_id = ?",
                (CORE,),
            )
            mark_wake_wanted(transaction, CORE, NOW)
            claimed = claim_wake(
                transaction,
                CORE,
                NOW,
                WakeLimits(600, 3, 90),
                "wake-on-alpha",
                "/alpha/logs/wake/wake-on-alpha",
            )
            assert claimed is not None
        automatic_answer(store, SECOND, CORE, 1)
    with _acting(rig, BETA_TOKEN) as store, store.write() as transaction:
        insert_question(transaction, waiting_question(ON_BETA, member_id=CORE), now=NOW)


@pytest.fixture
def rig(tmp_path: Path) -> HubRig:
    built = build_rig(tmp_path)
    _seed(built)
    return built


def test_removing_a_machine_closes_its_questions_answers_and_wakes(
    rig: HubRig,
) -> None:
    rm_machine(rig.layout, "alpha", NOW)

    questions = rig.rows(
        "SELECT run_id, state, closed_reason, closed_detail, machine_id "
        "FROM questions ORDER BY run_id"
    )
    by_run = {row[0]: row[1:] for row in questions}
    for key in (FIRST, SECOND, THIRD):
        state, reason, detail, machine = by_run[key.run_id]
        assert (state, reason, machine) == ("closed", "machine_removed", None)
        assert "alpha" in str(detail)
    assert by_run[ON_BETA.run_id][0] == "waiting_on_pm"
    assert by_run[ON_BETA.run_id][3] is not None
    assert rig.rows("SELECT resume_outcome, resume_claim_id FROM answers") == [
        ("not_delivered", None)
    ]
    ((outcome, detail, log_stem, machine),) = rig.rows(
        "SELECT outcome, detail, log_stem, machine_id FROM wakes"
    )
    assert (outcome, log_stem, machine) == ("machine_removed", None, None)
    assert "alpha" in str(detail)


def test_a_later_answer_to_a_removed_machines_question_is_not_delivered(
    rig: HubRig,
) -> None:
    rm_machine(rig.layout, "alpha", NOW)

    reply = rig.call(
        "answer",
        {"run_id": FIRST.run_id, "text": "300 lines"},
        token=BETA_TOKEN,
        extra={"via": "cli"},
    )

    done = result_of(reply)
    assert isinstance(done, DoneReply), done
    result: dict[str, Any] = done.result["result"]  # type: ignore[assignment]
    assert result["outcome"] == "recorded"
    assert result["resume"]["outcome"] == "not_delivered"
    assert result["resume"]["detail"] is not None


def test_a_wake_wrapper_whose_machine_was_removed_stops_its_command_at_its_next_step(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    with InProcessHub(tmp_path / "hub") as hub:
        hub.rig.follows = lambda: NOW
        join(line_for(hub), set_aside_local=False)
        with _acting(hub.rig, ALPHA_TOKEN) as store:
            seed_claimed_wake(store, tmp_path, "sleep 30", checkout)
        started: list[int] = []

        def popen_then_remove(*args: Any, **kwargs: Any) -> Any:
            child = contained_popen(*args, **kwargs)
            started.append(child.pid)
            rm_machine(hub.rig.layout, "alpha", NOW)
            return child

        steps = steps_on(DOOR, store, StepEdges(lambda: NOW, _no_config))
        with pytest.raises(HubRefusedError):
            run_wake(steps, WAKE_ID, popen=popen_then_remove)

    (pid,) = started
    assert wait_until(lambda: process_is_gone(pid))


def _no_config() -> Any:
    raise AssertionError("a wake step loaded the config")
