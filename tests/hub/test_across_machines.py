"""Work that belongs to a machine, across two joined machines (262 D7, D8, D10, D12).

Both machines run in this process against one in-process hub (``two_homes``): each is
its own home and its own edges, so what one starts the other never does.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from operations.handle_rig import KEY, PAUSE, QUESTION, RUNNING_DOC
from store.decision_support import CORE, LINT, NAMES
from store.seed import insert_checkout

from amoeba import wiring
from amoeba.answering.values import DeclineReason
from amoeba.operations.answer import AnswerOutcome, AnswerResult
from amoeba.operations.message_results import SendResult
from amoeba.operations.names import Door, OperationName
from amoeba.operations.resume_run import RESUME_RUN_COMMAND, run_resume
from amoeba.operations.steps.models import CLAIM_WORK
from amoeba.operations.steps.models_work import ClaimWorkRequest, WakeItem
from amoeba.store.machines import acting_machine_id
from amoeba.store.models import Session
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.store.sessions import upsert_session
from amoeba.store.vocabulary import ResumeOutcome
from amoeba.wiring_steps import DoorSteps, LastReply
from hub.two_homes import ALPHA, BETA, TwoHomes, two_homes

COMMAND = "wake-agent --max-seconds 60"


@pytest.fixture
def homes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TwoHomes]:
    with two_homes(tmp_path, monkeypatch, (CORE, LINT)) as both:
        yield both


def _paused_question(homes: TwoHomes, machine: str) -> None:
    """The fixture pipeline's pause, recorded on ``machine`` and waiting on the PM."""
    checkout = str(homes.machines[machine].directory)
    with homes.seeded(machine) as store, store.write() as transaction:
        insert_question(
            transaction,
            NewQuestion(
                key=KEY,
                member_id=CORE,
                question=QUESTION,
                checkout=checkout,
                slice_label=None,
                source_commit=None,
                passages=None,
                answering_run_id=None,
                waiting_reason=DeclineReason.ANSWER_LIMIT_REACHED,
                waiting_detail="needs the PM",
            ),
            now=homes.clock(),
        )


def test_a_pause_on_alpha_answered_from_beta_is_resumed_by_alphas_next_call(
    homes: TwoHomes,
) -> None:
    _paused_question(homes, ALPHA)

    beta = homes.use(BETA)
    answered = wiring.invoke(
        OperationName.ANSWER, {"run_id": KEY.run_id, "text": "300"}, None, Door.CLI
    )

    assert isinstance(answered, AnswerResult)
    assert answered.outcome is AnswerOutcome.RECORDED
    assert answered.resume is None
    assert answered.waiting_on_machine is not None
    assert answered.waiting_on_machine.machine == ALPHA
    assert answered.waiting_on_machine.last_called_at is not None
    assert beta.spawned == []

    alpha = homes.use(ALPHA)
    wiring.invoke(OperationName.DECISIONS, {}, None, Door.CLI)
    (started,) = alpha.spawned
    assert started[1] == RESUME_RUN_COMMAND
    seq, claim_id = int(started[2]), started[3]

    alpha.polls[KEY.run_id] = [PAUSE, PAUSE, RUNNING_DOC]
    result = run_resume(DoorSteps(LastReply()), alpha.deps, seq, claim_id)

    assert result is not None and result.outcome is ResumeOutcome.RESUMED
    assert homes.hub.rig.rows("SELECT resume_outcome FROM answers") == [("resumed",)]
    assert beta.spawned == []


def _wakeable_on(homes: TwoHomes, machine: str) -> None:
    """``LINT`` has a checkout with a wake command on ``machine`` only."""
    with homes.seeded(machine) as store, store.write() as transaction:
        updated = transaction.execute(
            "UPDATE checkouts SET wake_command = ? WHERE member_id = ? "
            "AND machine_id = ?",
            (COMMAND, LINT, acting_machine_id(transaction)),
        )
        if updated.rowcount == 0:
            insert_checkout(
                transaction,
                member_id=LINT,
                cf_project_id=LINT,
                path=str(homes.machines[machine].directory),
                wake_command=COMMAND,
                now=homes.clock(),
            )


def _send(homes: TwoHomes, request_id: str = "ask") -> SendResult:
    alpha = homes.use(ALPHA)
    sent = wiring.invoke(
        OperationName.SEND,
        {"id": request_id, "to": NAMES[LINT], "subject": "s", "body": "b"},
        alpha.directory,
        Door.CLI,
    )
    assert isinstance(sent, SendResult)
    return sent


def test_a_wake_only_another_machine_can_start_waits_names_it_and_expires(
    homes: TwoHomes,
) -> None:
    _wakeable_on(homes, BETA)

    sent = _send(homes)

    assert sent.woke is None
    assert [w.machine for w in sent.wake_waiting_on] == [BETA]
    assert homes.machines[ALPHA].spawned == []
    config = homes.hub.rig.config()
    homes.clock.advance(config.request_open_ttl_hours * 3600 + 1)
    homes.use(ALPHA)
    wiring.invoke(OperationName.STATUS, {}, homes.machines[ALPHA].directory, Door.CLI)
    assert homes.hub.rig.rows("SELECT state FROM messages") == [("expired",)]


def test_a_live_session_on_beta_holds_off_a_wake_from_alpha(homes: TwoHomes) -> None:
    _wakeable_on(homes, ALPHA)
    with homes.seeded(BETA) as store, store.write() as transaction:
        upsert_session(
            transaction,
            Session(
                session_id="session-on-beta",
                member_id=LINT,
                client="claude-code",
                directory="/beta/lint",
                started_at=homes.clock(),
                heartbeat_at=homes.clock(),
                push_confirmed_at=homes.clock(),
            ),
        )

    sent = _send(homes)
    claimed = DoorSteps(LastReply()).run(
        CLAIM_WORK, ClaimWorkRequest(logs_dir=str(homes.machines[ALPHA].home / "logs"))
    )

    assert sent.woke is None
    assert not [item for item in claimed.items if isinstance(item, WakeItem)]
    assert homes.machines[ALPHA].spawned == []


def _old_log(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("old", encoding="utf-8")
    os.utime(path, (1_000_000_000, 1_000_000_000))
    return path


def test_each_machine_prunes_its_own_old_logs_through_the_door_and_keeps_open_ones(
    homes: TwoHomes,
) -> None:
    _paused_question(homes, ALPHA)
    files: dict[str, tuple[Path, Path]] = {}
    for name, machine in homes.machines.items():
        logs = machine.deps.logs_dir
        files[name] = (
            _old_log(logs / "wake" / "old-wake.stdout.log"),
            _old_log(logs / "resume" / KEY.run_id / "1-old.stdout.log"),
        )

    for name in homes.machines:
        homes.use(name)
        wiring.invoke(OperationName.DECISIONS, {}, None, Door.CLI)

    alpha_wake, alpha_open = files[ALPHA]
    beta_wake, beta_resume = files[BETA]
    assert not alpha_wake.exists() and not beta_wake.exists()
    assert alpha_open.exists(), "alpha's open question keeps its run's logs"
    assert not beta_resume.exists(), "the run is open on alpha, not on beta"
