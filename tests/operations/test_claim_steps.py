"""The question claim steps: the winning and the losing case of each row of D4's
table (slice 262, 4.2)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.question_support import (
    ANSWERING_RUN,
    KEY,
    MEMBER_ID,
    NOW,
    PASSAGE,
    claimed_question,
    insert_held_row,
    seed_members,
    waiting_question,
)
from store_open import open_local_store
from user_configs import user_config

from amoeba.answering.values import DeclineReason
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.models import (
    QUESTION_CLAIM_HELD,
    QUESTION_HOLD,
    QUESTION_INSERT,
    QUESTION_REPLACE_CLAIM,
    QUESTION_WAIT,
)
from amoeba.operations.steps.models_pause import (
    EvidenceModel,
    LossKind,
    PassageRefModel,
    QuestionClaimHeldRequest,
    QuestionHoldRequest,
    QuestionInsertRequest,
    QuestionReplaceClaimRequest,
    QuestionWaitRequest,
)
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.messages import insert_request
from amoeba.store.models import QuestionRecord
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState, RequestState

PASSAGES = (PassageRefModel.of(PASSAGE),)
NEW_RUN = "amoeba-20261110T120000Z-bbbbbbbbbbbb"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


@pytest.fixture
def steps(store: Store) -> LocalSteps:
    return LocalSteps(store, StepEdges(lambda: NOW, user_config))


def _row(store: Store) -> QuestionRecord | None:
    with store.read() as transaction:
        return get_question(transaction, KEY)


def _insert(**fields: object) -> QuestionInsertRequest:
    base: dict[str, object] = {
        "run_id": KEY.run_id,
        "paused_at": KEY.paused_at,
        "member_id": MEMBER_ID,
        "question": "q",
        "checkout": "/work/a",
        "slice_label": "none",
        "source_commit": "abc",
        "passages": PASSAGES,
        "answering_run_id": ANSWERING_RUN,
        "waiting_reason": None,
        "waiting_detail": None,
    }
    return QuestionInsertRequest.model_validate({**base, **fields})


def test_question_insert_wins_when_no_row_exists_and_loses_when_one_does(
    store: Store, steps: LocalSteps
) -> None:
    won = steps.run(QUESTION_INSERT, _insert())
    lost = steps.run(QUESTION_INSERT, _insert(answering_run_id=NEW_RUN))

    assert (won.inserted, lost.inserted) == (True, False)
    row = _row(store)
    assert row is not None
    assert (row.state, row.answering_run_id) == (QuestionState.CLAIMED, ANSWERING_RUN)


def test_question_insert_can_insert_waiting_with_a_reason(
    store: Store, steps: LocalSteps
) -> None:
    steps.run(
        QUESTION_INSERT,
        _insert(
            answering_run_id=None,
            passages=None,
            waiting_reason=DeclineReason.ANSWER_LIMIT_REACHED,
            waiting_detail="3 answers",
        ),
    )

    row = _row(store)
    assert row is not None
    assert row.state is QuestionState.WAITING_ON_PM
    assert row.waiting_reason is DeclineReason.ANSWER_LIMIT_REACHED


def _hold(request_id: str = "request-a") -> QuestionHoldRequest:
    return QuestionHoldRequest(
        run_id=KEY.run_id,
        paused_at=KEY.paused_at,
        member_id=MEMBER_ID,
        question="q",
        checkout="/work/a",
        request_id=request_id,
    )


def _request_open(store: Store) -> None:
    with store.write() as transaction:
        insert_request(
            transaction,
            message_id="request-a",
            from_member=MEMBER_ID,
            to_member="member-b",
            parent_id=None,
            parent_depth=None,
            subject="s",
            body="b",
            ttl=timedelta(days=1),
            now=NOW,
        )


def test_question_hold_wins_once_and_returns_its_requests_state(
    store: Store, steps: LocalSteps
) -> None:
    _request_open(store)

    won = steps.run(QUESTION_HOLD, _hold())
    lost = steps.run(QUESTION_HOLD, _hold())

    assert won.inserted
    assert won.request is not None
    assert won.request.state is RequestState.OPEN
    assert not lost.inserted
    assert lost.request is None


def test_question_hold_reports_a_request_that_is_not_stored(
    store: Store, steps: LocalSteps
) -> None:
    won = steps.run(QUESTION_HOLD, _hold("gone"))

    assert won.request is not None
    assert won.request.state is None


def _claim_held(run: str = NEW_RUN) -> QuestionClaimHeldRequest:
    return QuestionClaimHeldRequest(
        run_id=KEY.run_id,
        paused_at=KEY.paused_at,
        answering_run_id=run,
        passages=PASSAGES,
        slice_label="none",
        source_commit="abc",
    )


def test_question_claim_held_wins_from_held_and_a_second_loses_to_the_claim(
    store: Store, steps: LocalSteps
) -> None:
    with store.write() as transaction:
        insert_held_row(transaction)

    won = steps.run(QUESTION_CLAIM_HELD, _claim_held())
    lost = steps.run(QUESTION_CLAIM_HELD, _claim_held("another-run"))

    assert won.claimed
    assert (lost.claimed, lost.lost_to) == (False, LossKind.CLAIM)


def test_question_claim_held_says_an_answer_or_dismissal_won(
    store: Store, steps: LocalSteps
) -> None:
    with store.write() as transaction:
        insert_held_row(transaction)
        transaction.execute("UPDATE questions SET state = 'closed'")

    lost = steps.run(QUESTION_CLAIM_HELD, _claim_held())

    assert (lost.claimed, lost.lost_to) == (False, LossKind.ENDED)


def _replace(old: str = ANSWERING_RUN) -> QuestionReplaceClaimRequest:
    return QuestionReplaceClaimRequest(
        run_id=KEY.run_id,
        paused_at=KEY.paused_at,
        old_answering_run_id=old,
        new_answering_run_id=NEW_RUN,
        passages=PASSAGES,
    )


def test_two_replace_claims_for_one_stale_claim_apply_once(
    store: Store, steps: LocalSteps
) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)

    first = steps.run(QUESTION_REPLACE_CLAIM, _replace())
    second = steps.run(QUESTION_REPLACE_CLAIM, _replace())

    assert (first.applied, second.applied) == (True, False)
    row = _row(store)
    assert row is not None
    assert row.answering_run_id == NEW_RUN


def _wait(run: str | None) -> QuestionWaitRequest:
    return QuestionWaitRequest(
        run_id=KEY.run_id,
        paused_at=KEY.paused_at,
        answering_run_id=run,
        reason=DeclineReason.ANSWERING_RUN_STALLED,
        detail="no result",
        evidence=EvidenceModel(reason="why"),
    )


def test_question_wait_moves_the_named_claim_and_loses_to_another_run(
    store: Store, steps: LocalSteps
) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)

    lost = steps.run(QUESTION_WAIT, _wait("someone-elses-run"))
    won = steps.run(QUESTION_WAIT, _wait(ANSWERING_RUN))

    assert (lost.applied, won.applied) == (False, True)
    row = _row(store)
    assert row is not None
    assert row.state is QuestionState.WAITING_ON_PM
    assert row.evidence is not None and row.evidence.reason == "why"


def test_question_wait_moves_a_held_row_and_loses_once_it_is_not_held(
    store: Store, steps: LocalSteps
) -> None:
    with store.write() as transaction:
        insert_held_row(transaction)

    won = steps.run(QUESTION_WAIT, _wait(None))
    lost = steps.run(QUESTION_WAIT, _wait(None))

    assert (won.applied, lost.applied) == (True, False)


def test_waiting_question_rows_are_not_claimable_by_wait_for_a_claim(
    store: Store, steps: LocalSteps
) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)

    assert not steps.run(QUESTION_WAIT, _wait(ANSWERING_RUN)).applied
