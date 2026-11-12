"""``dismiss`` (slice 228, D5)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.question_support import (
    ANSWERING_RUN,
    KEY,
    NOW,
    claimed_question,
    seed_members,
    waiting_question,
)

from amoeba.answering.values import AnsweringEvidence, DeclineReason
from amoeba.operations.dismiss import (
    DismissOutcome,
    DismissRejection,
    DismissResult,
    dismiss,
)
from amoeba.store.answers import (
    Lost,
    add_pm_answer,
    answers_of,
    latest_answer,
    mark_resume_started,
    record_resume,
    settle_answered,
)
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.questions import get_question, insert_question, settle_waiting
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome

LATER = NOW + timedelta(minutes=5)
REASON = "not needed tonight"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _dismiss(store: Store, **fields: str) -> DismissResult:
    document = {"run_id": KEY.run_id, "reason": REASON, **fields}
    return dismiss(store, document, clock=lambda: LATER)


def _row(store: Store, key: QuestionKey = KEY) -> QuestionRecord:
    with store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None
    return row


def _answered(store: Store, outcome: ResumeOutcome | None) -> int:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)
        seq = add_pm_answer(transaction, KEY, "an answer", now=NOW)
        if outcome is not None:
            record_resume(transaction, seq, outcome, detail="why", log="/log", at=NOW)
    return seq


@pytest.mark.parametrize("seeded", ["claimed", "waiting", "at_the_limit"])
def test_it_closes_a_claimed_waiting_or_limit_question(
    store: Store, seeded: str
) -> None:
    new = claimed_question() if seeded == "claimed" else waiting_question()
    with store.write() as transaction:
        insert_question(transaction, new, now=NOW)
    if seeded == "at_the_limit":
        assert _row(store).waiting_reason is DeclineReason.ANSWER_LIMIT_REACHED

    result = _dismiss(store)

    assert result.outcome is DismissOutcome.DISMISSED
    assert result.key == KEY
    assert result.closed_reason is ClosedReason.DISMISSED
    assert result.closed_detail == REASON
    row = _row(store)
    assert row.state is QuestionState.CLOSED
    assert row.closed_detail == REASON
    assert row.closed_at == LATER


def test_a_repeat_is_unchanged_and_names_the_existing_reason(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)
    _dismiss(store)

    again = _dismiss(store, reason="a different reason")

    assert again.outcome is DismissOutcome.UNCHANGED
    assert again.closed_reason is ClosedReason.DISMISSED
    assert again.closed_detail == REASON
    assert _row(store).closed_detail == REASON


@pytest.mark.parametrize("outcome", [None, ResumeOutcome.REFUSED])
def test_an_unresumed_answer_is_dismissed_and_not_delivered(
    store: Store, outcome: ResumeOutcome | None
) -> None:
    _answered(store, outcome)

    result = _dismiss(store)

    assert result.outcome is DismissOutcome.DISMISSED
    assert _row(store).state is QuestionState.CLOSED
    with store.read() as transaction:
        answer = latest_answer(transaction, KEY)
    assert answer is not None
    assert answer.resume_outcome is ResumeOutcome.NOT_DELIVERED
    assert answer.resume_detail == "dismissed"


def test_an_answer_whose_resume_is_in_flight_is_not_dismissed(store: Store) -> None:
    seq = _answered(store, None)
    with store.write() as transaction:
        assert mark_resume_started(transaction, seq, now=NOW)

    result = _dismiss(store)

    assert result.rejection is DismissRejection.NOT_OPEN
    assert "in flight" in result.problems[0]
    assert _row(store).state is QuestionState.ANSWERED
    with store.read() as transaction:
        answer = latest_answer(transaction, KEY)
    assert answer is not None
    assert answer.resume_outcome is None


def test_a_resumed_answer_is_not_open_and_the_detail_points_to_retract(
    store: Store,
) -> None:
    _answered(store, ResumeOutcome.RESUMED)

    result = _dismiss(store)

    assert result.outcome is DismissOutcome.REJECTED
    assert result.rejection is DismissRejection.NOT_OPEN
    assert "delivered" in result.problems[0]
    assert "retract" in result.problems[0]
    assert _row(store).state is QuestionState.ANSWERED


def test_a_not_delivered_answer_is_not_open_and_the_detail_says_so(
    store: Store,
) -> None:
    _answered(store, ResumeOutcome.NOT_DELIVERED)

    result = _dismiss(store)

    assert result.rejection is DismissRejection.NOT_OPEN
    assert "never delivered" in result.problems[0]


def test_an_unknown_run_has_no_such_question(store: Store) -> None:
    result = dismiss(store, {"run_id": "nope", "reason": REASON}, clock=lambda: LATER)

    assert result.outcome is DismissOutcome.REJECTED
    assert result.rejection is DismissRejection.NO_SUCH_QUESTION


@pytest.mark.parametrize(
    "document",
    [
        {"run_id": "run-1", "reason": "   "},
        {"run_id": "run-1"},
        {"reason": "x"},
        {"run_id": "run-1", "reason": "x", "extra": 1},
        "not a mapping",
        ["run-1", "x"],
        None,
    ],
)
def test_a_malformed_document_is_rejected(store: Store, document: object) -> None:
    result = dismiss(store, document, clock=lambda: LATER)

    assert result.outcome is DismissOutcome.REJECTED
    assert result.rejection is DismissRejection.MALFORMED
    assert result.problems


def test_a_paused_at_picks_that_question_not_the_latest(store: Store) -> None:
    later = QuestionKey(KEY.run_id, "2026-11-10T13:00:00+00:00")
    with store.write() as transaction:
        insert_question(transaction, waiting_question(KEY), now=NOW)
        insert_question(transaction, waiting_question(later), now=LATER)

    result = _dismiss(store, paused_at=KEY.paused_at)

    assert result.key == KEY
    assert _row(store, KEY).state is QuestionState.CLOSED
    assert _row(store, later).state is QuestionState.WAITING_ON_PM


def test_an_answering_run_settling_after_the_dismissal_writes_nothing(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)
    _dismiss(store)

    settled = settle_answered(
        store,
        KEY,
        ANSWERING_RUN,
        answer="late",
        cited=(),
        evidence=AnsweringEvidence(),
        gate=lambda _prior: None,
        now=LATER,
    )
    with store.write() as transaction:
        waited = settle_waiting(
            transaction,
            KEY,
            ANSWERING_RUN,
            reason=DeclineReason.CHECK_SAID_NO,
            detail=None,
            evidence=None,
            now=LATER,
        )
    with store.read() as transaction:
        answers = answers_of(transaction, KEY)

    assert isinstance(settled, Lost)
    assert not waited
    assert answers == ()
    assert _row(store).state is QuestionState.CLOSED


def test_a_reason_with_shell_metacharacters_round_trips_as_data(
    store: Store,
) -> None:
    reason = "$(touch /tmp/x); `id` | cat > /dev/null && echo 'a' \"b\" \\n %s"
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)

    result = _dismiss(store, reason=reason)

    assert result.closed_detail == reason
    assert _row(store).closed_detail == reason
