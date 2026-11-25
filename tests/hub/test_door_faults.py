"""Faults through the door: lost replies, a stopped hub, claims that run out (262 D10,
D11). ``two_homes`` drops replies after commit and the hub reads the test's clock."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from operations.handle_rig import KEY, PAUSE, RUNNING_DOC
from store.decision_support import CORE, FIRST, LINT, automatic_answer
from store.question_support import claimed_question
from store.seed import mark_wake_wanted

from amoeba import wiring, wiring_door, wiring_steps
from amoeba.cli.main import EXIT_ERROR, main
from amoeba.client.errors import HubUnreachableError
from amoeba.config.user_config import ConfigError, UserConfig
from amoeba.operations.names import Door, OperationName
from amoeba.operations.resume_attempt import attempt_path, write_started
from amoeba.operations.resume_run import RESUME_RUN_COMMAND, run_resume
from amoeba.operations.steps.limits import (
    MAX_AUTOMATIC_STARTS,
    pause_claim_seconds,
    resume_claim_seconds,
    wake_limits,
)
from amoeba.operations.steps.models import CLAIM_WORK, RESUME_RECORD
from amoeba.operations.steps.models_resume import ResumeRecordRequest
from amoeba.operations.steps.models_work import (
    ClaimWorkRequest,
    HandlePauseItem,
    ResumeItem,
    WakeItem,
    WorkItem,
)
from amoeba.store.questions import insert_question
from amoeba.store.vocabulary import ResumeOutcome
from amoeba.wire.times import DOOR_VERSION, DoorTimes
from amoeba.wiring_steps import DoorSteps, LastReply
from hub.two_homes import ALPHA, BETA, TwoHomes, two_homes

FAST = DoorTimes(
    connect_seconds=0.2, read_seconds=0.5, retry_seconds=0.8, retry_pause_seconds=0.1
)
COMMAND = "wake-agent --max-seconds 60"


@pytest.fixture
def homes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TwoHomes]:
    with two_homes(tmp_path, monkeypatch, (CORE, LINT)) as both:
        yield both


def _config(homes: TwoHomes) -> UserConfig:
    return homes.hub.rig.config()


def _claim(homes: TwoHomes, machine: str = ALPHA) -> tuple[WorkItem, ...]:
    homes.use(machine)
    logs = str(homes.machines[machine].deps.logs_dir)
    reply = DoorSteps(LastReply(), FAST).run(
        CLAIM_WORK, ClaimWorkRequest(logs_dir=logs)
    )
    return reply.items


def _claim_lost(homes: TwoHomes) -> None:
    """A ``claim_work`` the hub applied whose every reply was lost."""
    homes.dropper.count = 1_000
    with pytest.raises(HubUnreachableError):
        _claim(homes)
    homes.dropper.count = 0


def _kinds(items: tuple[WorkItem, ...], kind: type) -> list[WorkItem]:
    return [item for item in items if isinstance(item, kind)]


def test_a_lost_claim_hands_the_resume_out_again_only_once_its_claim_runs_out(
    homes: TwoHomes,
) -> None:
    with homes.seeded(ALPHA) as store:
        automatic_answer(store, FIRST, CORE, 1)

    _claim_lost(homes)
    limit = resume_claim_seconds(_config(homes))
    homes.clock.advance(limit - 1)
    early = _claim(homes)
    homes.clock.advance(1)
    late = _claim(homes)

    assert _kinds(early, ResumeItem) == []
    assert len(_kinds(late, ResumeItem)) == 1


def test_a_lost_claim_hands_a_dead_claim_out_again_after_the_start_wait(
    homes: TwoHomes,
) -> None:
    config = _config(homes)
    stale = homes.clock() - timedelta(seconds=pause_claim_seconds(config))
    with homes.seeded(ALPHA) as store, store.write() as transaction:
        insert_question(transaction, claimed_question(FIRST, member_id=CORE), now=stale)

    _claim_lost(homes)
    homes.clock.advance(config.answering_wait_seconds - 1)
    early = _claim(homes)
    homes.clock.advance(1)
    late = _claim(homes)

    assert _kinds(early, HandlePauseItem) == []
    assert len(_kinds(late, HandlePauseItem)) == 1


def test_a_lost_claim_hands_the_wake_out_again_after_its_deadline(
    homes: TwoHomes,
) -> None:
    with homes.seeded(ALPHA) as store, store.write() as transaction:
        transaction.execute(
            "UPDATE checkouts SET wake_command = ? WHERE member_id = ?",
            (COMMAND, LINT),
        )
        mark_wake_wanted(transaction, LINT, homes.clock())

    _claim_lost(homes)
    homes.clock.advance(wake_limits(_config(homes), DOOR_VERSION).timeout_seconds - 1)
    early = _claim(homes)
    homes.clock.advance(2)
    late = _claim(homes)

    assert _kinds(early, WakeItem) == []
    assert len(_kinds(late, WakeItem)) == 1


def test_a_resume_record_retried_across_a_hub_restart_is_recorded_once(
    homes: TwoHomes,
) -> None:
    with homes.seeded(ALPHA) as store:
        automatic_answer(store, FIRST, CORE, 1)
    (item,) = _kinds(_claim(homes), ResumeItem)
    assert isinstance(item, ResumeItem)
    record = ResumeRecordRequest(
        answer_seq=item.answer_seq,
        claim_id=item.claim_id,
        outcome=ResumeOutcome.RESUMED,
        detail=None,
        log="/alpha/logs/resume/run-1/1.stdout.log",
    )

    homes.hub.stop()
    with pytest.raises(HubUnreachableError):
        DoorSteps(LastReply(), FAST).run(RESUME_RECORD, record)
    homes.hub.start()
    others = _claim(homes, BETA) + _claim(homes, ALPHA)
    homes.use(ALPHA)
    first = DoorSteps(LastReply(), FAST).run(RESUME_RECORD, record)
    again = DoorSteps(LastReply(), FAST).run(RESUME_RECORD, record)

    assert _kinds(others, ResumeItem) == []
    assert first.outcome is again.outcome is ResumeOutcome.RESUMED
    assert again.wrote is False
    assert homes.hub.rig.rows(
        "SELECT resume_outcome, resume_claim_id FROM answers"
    ) == [("resumed", None)]


def test_with_the_hubs_config_broken_the_client_prints_the_work_problem(
    homes: TwoHomes, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> UserConfig:
        raise ConfigError("config.yaml: answering_wait_seconds: not a number")

    homes.hub.rig.config = broken
    homes.use(ALPHA)

    wiring.invoke(OperationName.DECISIONS, {}, None, Door.CLI)

    err = capsys.readouterr().err
    assert "could not tell whether this machine has work waiting" in err
    assert "answering_wait_seconds" in err


def test_status_whose_open_runs_fails_exits_3_and_makes_no_further_call(
    homes: TwoHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken() -> UserConfig:
        raise ConfigError("config.yaml: prune_after_days: not a number")

    names: list[str] = []
    for module in (wiring_steps, wiring_door):
        monkeypatch.setattr(module, "call", _counting(module.call, names))
    homes.hub.rig.config = broken
    alpha = homes.use(ALPHA)
    monkeypatch.chdir(alpha.directory)

    code = main(["status"])

    assert code == EXIT_ERROR
    assert names == ["open_runs"]


def _counting(real: Callable[..., dict[str, object]], names: list[str]) -> object:
    def counted(*args: object, **kwargs: object) -> dict[str, object]:
        names.append(str(args[2]))
        return real(*args, **kwargs)

    return counted


def _lose(monkeypatch: pytest.MonkeyPatch, step: str) -> None:
    """The next ``step`` call gets no reply and is not applied."""
    real = wiring_steps.call

    def lost(*args: object, **kwargs: object) -> dict[str, object]:
        if args[2] == step:
            monkeypatch.setattr(wiring_steps, "call", real)
            raise HubUnreachableError(f"no reply to {step}")
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(wiring_steps, "call", lost)


def _resume_item(homes: TwoHomes) -> ResumeItem:
    (item,) = _kinds(_claim(homes), ResumeItem)
    assert isinstance(item, ResumeItem)
    return item


def test_a_resumed_attempt_whose_record_got_no_reply_is_recorded_from_its_file(
    homes: TwoHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    with homes.seeded(ALPHA) as store:
        automatic_answer(store, KEY, CORE, 1)
    alpha = homes.machines[ALPHA]
    alpha.polls[KEY.run_id] = [PAUSE, PAUSE, RUNNING_DOC]
    first = _resume_item(homes)
    _lose(monkeypatch, "resume_record")

    with pytest.raises(HubUnreachableError):
        run_resume(
            DoorSteps(LastReply(), FAST), alpha.deps, first.answer_seq, first.claim_id
        )
    homes.clock.advance(resume_claim_seconds(_config(homes)))
    second = _resume_item(homes)
    result = run_resume(
        DoorSteps(LastReply(), FAST), alpha.deps, second.answer_seq, second.claim_id
    )

    assert result is not None and result.outcome is ResumeOutcome.RESUMED
    assert len([a for a in alpha.spawned if "--resume" in a]) == 1
    assert homes.hub.rig.rows("SELECT resume_outcome FROM answers") == [("resumed",)]


@pytest.mark.parametrize("next_call", [OperationName.LIST, OperationName.STATUS])
def test_an_attempt_killed_after_it_started_sq_is_recorded_resumed_by_the_next_call(
    homes: TwoHomes, next_call: OperationName
) -> None:
    with homes.seeded(ALPHA) as store:
        automatic_answer(store, KEY, CORE, 1)
    alpha = homes.use(ALPHA)
    item = _resume_item(homes)
    path = attempt_path(alpha.deps.logs_dir, KEY.run_id, item.answer_seq)
    write_started(path)  # the attempt died after starting ``sq run --resume``
    homes.clock.advance(resume_claim_seconds(_config(homes)))
    alpha.polls[KEY.run_id] = [RUNNING_DOC]

    wiring.invoke(next_call, {}, alpha.directory, Door.CLI)
    spawned = [a for a in alpha.spawned if a[1] == RESUME_RUN_COMMAND]
    seq, claim_id = int(spawned[-1][2]), spawned[-1][3]
    result = run_resume(DoorSteps(LastReply(), FAST), alpha.deps, seq, claim_id)

    assert result is not None and result.outcome is ResumeOutcome.RESUMED
    assert [a for a in alpha.spawned if "--resume" in a] == []
    assert homes.hub.rig.rows("SELECT resume_outcome FROM answers") == [("resumed",)]


def test_a_resume_whose_attempts_all_die_is_refused_after_three_then_not_delivered(
    homes: TwoHomes,
) -> None:
    with homes.seeded(ALPHA) as store:
        automatic_answer(store, KEY, CORE, 1)
    limit = resume_claim_seconds(_config(homes))
    handed = 0
    for _ in range(MAX_AUTOMATIC_STARTS):
        handed += len(_kinds(_claim(homes), ResumeItem))
        homes.clock.advance(limit)
    fourth = _claim(homes)

    assert handed == MAX_AUTOMATIC_STARTS
    assert _kinds(fourth, ResumeItem) == []
    assert homes.hub.rig.rows("SELECT resume_outcome FROM answers") == [("refused",)]
    homes.clock.advance(limit)
    alpha = homes.use(ALPHA)
    wiring.invoke(OperationName.STATUS, {}, alpha.directory, Door.CLI)
    assert homes.hub.rig.rows("SELECT resume_outcome FROM answers") == [
        ("not_delivered",)
    ]
