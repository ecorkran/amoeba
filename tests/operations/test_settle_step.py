"""``question_settle`` and ``pause_sources`` (slice 262, 4.3)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from store.question_support import (
    ANSWERING_RUN,
    KEY,
    MEMBER_ID,
    NOW,
    claimed_question,
    seed_members,
    waiting_question,
)
from store.seed import insert_checkout, insert_member, insert_program
from store_open import open_local_store
from user_configs import user_config

from amoeba.answering.values import DeclineReason
from amoeba.operations.steps.dispatch import StepEdges, run_step
from amoeba.operations.steps.models import PAUSE_SOURCES, QUESTION_SETTLE
from amoeba.operations.steps.models_pause import (
    EvidenceModel,
    PauseSourcesRequest,
    QuestionSettleReply,
    QuestionSettleRequest,
    SettleStatus,
)
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.answers import answers_of
from amoeba.store.machines import ActingMachine, invite_machine, the_owner
from amoeba.store.models import QuestionKey
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState

CONFIG = user_config()
EDGES = StepEdges(lambda: NOW, lambda: CONFIG)
ANSWER = "The limit is 300 lines."


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        with opened.write() as transaction:
            insert_question(transaction, claimed_question(), now=NOW)
        yield opened


def _settle(
    run: str = ANSWERING_RUN, answer: str = ANSWER, key: QuestionKey = KEY
) -> QuestionSettleRequest:
    return QuestionSettleRequest(
        run_id=key.run_id,
        paused_at=key.paused_at,
        answering_run_id=run,
        answer=answer,
        cited=("r1",),
        evidence=EvidenceModel(proposed_answer=answer, cited=("r1",), verdict="yes"),
    )


def test_an_answered_settle_writes_the_answer_and_returns_its_resume_claim(
    store: Store,
) -> None:
    reply = LocalSteps(store, EDGES).run(QUESTION_SETTLE, _settle())

    assert reply.status is SettleStatus.ANSWERED
    assert reply.claim is not None
    assert (reply.claim.answer_seq, reply.claim.answer_text) == (
        reply.answer_seq,
        ANSWER,
    )
    assert reply.claim.resume_wait_seconds == CONFIG.resume_wait_seconds
    with store.read() as transaction:
        (answer,) = answers_of(transaction, KEY)
        row = get_question(transaction, KEY)
    assert answer.resume_claim_id == reply.claim.claim_id
    assert row is not None and row.state is QuestionState.ANSWERED


def test_a_gate_refusal_waits_on_the_pm_with_the_reason(store: Store) -> None:
    reply = LocalSteps(store, EDGES).run(
        QUESTION_SETTLE, _settle(answer="Fine, go ahead and git push it.")
    )

    assert reply.status is SettleStatus.WAITING
    assert reply.reason is DeclineReason.RESERVED_TERM
    assert reply.claim is None
    with store.read() as transaction:
        row = get_question(transaction, KEY)
        assert answers_of(transaction, KEY) == ()
    assert row is not None
    assert row.state is QuestionState.WAITING_ON_PM
    assert row.waiting_reason is DeclineReason.RESERVED_TERM
    assert row.evidence is not None and row.evidence.verdict == "yes"


def test_a_settle_for_a_claim_that_is_gone_starts_no_resume(store: Store) -> None:
    reply = LocalSteps(store, EDGES).run(QUESTION_SETTLE, _settle(run="another-run"))

    assert reply.status is SettleStatus.SUPERSEDED
    assert reply.claim is None
    with store.read() as transaction:
        assert answers_of(transaction, KEY) == ()


def test_two_settles_for_one_run_with_one_answer_left_answer_once(
    tmp_path: Path,
) -> None:
    path = tmp_path / "amoeba.sqlite3"
    second = QuestionKey(KEY.run_id, "2026-11-10T11:05:00+00:00")
    with open_local_store(path) as first:
        seed_members(first)
        with first.write() as transaction:
            insert_question(transaction, claimed_question(), now=NOW)
            insert_question(
                transaction,
                claimed_question(second, answering_run_id="second-run"),
                now=NOW,
            )
            for index in range(CONFIG.answer_limit - 1):
                earlier = f"2026-11-10T0{index}:00:00+00:00"
                insert_question(
                    transaction,
                    waiting_question(QuestionKey(KEY.run_id, earlier)),
                    now=NOW,
                )
                transaction.execute(
                    "INSERT INTO answers (run_id, paused_at, answered_by, answer, "
                    "recorded_at, owner_id) VALUES (?, ?, 'answerer', 'a', ?, "
                    "(SELECT owner_id FROM owners))",
                    (KEY.run_id, earlier, "2026-11-10T10:00:00+00:00"),
                )
    barrier = threading.Barrier(2)
    replies: list[QuestionSettleReply] = []

    def settle_one(request: QuestionSettleRequest) -> None:
        with open_local_store(path) as mine:
            barrier.wait()
            reply = run_step(
                QUESTION_SETTLE.name, mine, request.model_dump(mode="json"), EDGES
            )
            assert isinstance(reply, QuestionSettleReply)
            replies.append(reply)

    threads = [
        threading.Thread(target=settle_one, args=(_settle(),)),
        threading.Thread(
            target=settle_one, args=(_settle(run="second-run", key=second),)
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    statuses = sorted(reply.status for reply in replies)
    assert statuses == [SettleStatus.ANSWERED, SettleStatus.WAITING]
    waiting = next(r for r in replies if r.status is SettleStatus.WAITING)
    assert waiting.reason is DeclineReason.ANSWER_LIMIT_REACHED


def test_pause_sources_returns_the_calling_machines_checkout_ids_never_member_ids(
    tmp_path: Path,
) -> None:
    with open_local_store(tmp_path / "amoeba.sqlite3") as store:
        with store.write() as transaction:
            insert_program(
                transaction,
                program_id="demo",
                concept_member="concept-member",
                concept_path="CONCEPT.md",
                registered_at=NOW,
                updated_at=NOW,
            )
            for member in (MEMBER_ID, "concept-member"):
                insert_member(
                    transaction,
                    project_id=member,
                    program_id="demo",
                    rules_paths=(),
                    authorize_allow=(),
                    authorize_deny=(),
                    registered_at=NOW,
                    updated_at=NOW,
                )
            insert_checkout(
                transaction,
                member_id="concept-member",
                cf_project_id="cf-concept-here",
                path="/here/concept",
                wake_command="secret-command",
                now=NOW,
            )
            invite_machine(transaction, "beta", "c" * 64, NOW)
            beta = int(
                transaction.execute(
                    "SELECT machine_id FROM machines WHERE name = 'beta'"
                ).fetchone()[0]
            )
            owner = the_owner(transaction)
        store.act_as(ActingMachine(beta, owner))
        with store.write() as transaction:
            insert_checkout(
                transaction,
                member_id="concept-member",
                cf_project_id="cf-concept-beta",
                path="/beta/concept",
                now=NOW,
            )
        local_id = _local(store)

        store.act_as(ActingMachine(local_id, owner))
        reply = LocalSteps(store, EDGES).run(
            PAUSE_SOURCES, PauseSourcesRequest(member_id=MEMBER_ID)
        )

    assert reply.concept_checkout is not None
    assert reply.concept_checkout.cf_project_id == "cf-concept-here"
    assert reply.concept_checkout.path == "/here/concept"
    assert "secret-command" not in reply.model_dump_json()
    assert {member.project_id for member in reply.members} == {
        MEMBER_ID,
        "concept-member",
    }


def _local(store: Store) -> int:
    with store.read() as transaction:
        row = transaction.execute(
            "SELECT machine_id FROM machines WHERE name = 'local'"
        ).fetchone()
    assert row is not None
    return int(row[0])
