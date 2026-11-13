"""``waiting_reason`` and ``waiting_detail`` survive a question being answered
(slice 224, D5): ``decisions`` shows why a question waited on the PM after the PM
answered it."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.answering.values import AnsweringEvidence, DeclineReason
from amoeba.store.answers import Settled, add_pm_answer, settle_answered
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState
from store.question_support import (
    ANSWERING_RUN,
    KEY,
    NOW,
    claimed_question,
    seed_members,
    waiting_question,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _retained(store: Store) -> tuple[QuestionState, DeclineReason | None, str | None]:
    with store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    return record.state, record.waiting_reason, record.waiting_detail


def test_a_pm_answer_to_a_waiting_question_keeps_its_reason_and_detail(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)
        add_pm_answer(transaction, KEY, "Use 300 lines.", now=NOW, via=None)

    assert _retained(store) == (
        QuestionState.ANSWERED,
        DeclineReason.ANSWER_LIMIT_REACHED,
        "limit 3",
    )


def test_an_automatic_settle_keeps_the_reason_and_detail_the_row_holds(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)
        # A claim that once waited: the columns are set, the state is claimed.
        transaction.execute(
            "UPDATE questions SET waiting_reason = ?, waiting_detail = ?",
            (DeclineReason.ANSWER_LIMIT_REACHED.value, "limit 3"),
        )

    settled = settle_answered(
        store,
        KEY,
        ANSWERING_RUN,
        answer="Use 300 lines.",
        cited=("r1",),
        evidence=AnsweringEvidence(),
        gate=lambda _prior: None,
        now=NOW,
    )

    assert isinstance(settled, Settled)
    assert _retained(store) == (
        QuestionState.ANSWERED,
        DeclineReason.ANSWER_LIMIT_REACHED,
        "limit 3",
    )
