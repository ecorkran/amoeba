"""Question reads, the claim insert and the compare-and-set moves (slice 223, 1.6)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.answering.values import AnsweringEvidence, DeclineReason
from amoeba.store.models import QuestionKey
from amoeba.store.questions import (
    any_answering_run_id,
    get_question,
    insert_question,
    latest_question,
    replace_claim,
    settle_waiting,
)
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState
from store.question_support import (
    ANSWERING_RUN,
    KEY,
    NOW,
    PASSAGE,
    claimed_question,
    seed_members,
    waiting_question,
)

OTHER_RUN = "amoeba-20261110T120000Z-bbbbbbbbbbbb"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def test_a_claimed_row_reads_back_whole(store: Store) -> None:
    with store.write() as transaction:
        assert insert_question(transaction, claimed_question(), now=NOW)

    with store.read() as transaction:
        record = get_question(transaction, KEY)

    assert record is not None
    assert record.state is QuestionState.CLAIMED
    assert record.answering_run_id == ANSWERING_RUN
    assert record.passages == (PASSAGE,)
    assert record.slice_label == "223 pause-handling"
    assert record.source_commit == "abc123"
    assert record.waiting_reason is None
    assert record.claimed_at == NOW


def test_a_waiting_row_carries_its_reason_and_no_claim(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)

    with store.read() as transaction:
        record = get_question(transaction, KEY)

    assert record is not None
    assert record.state is QuestionState.WAITING_ON_PM
    assert record.waiting_reason is DeclineReason.ANSWER_LIMIT_REACHED
    assert record.waiting_detail == "limit 3"
    assert record.answering_run_id is None
    assert record.passages is None


def test_a_new_question_needs_exactly_one_of_claim_and_reason() -> None:
    with pytest.raises(ValueError, match="claimed"):
        replace(claimed_question(), waiting_reason=DeclineReason.CHECK_SAID_NO)
    with pytest.raises(ValueError, match="claimed"):
        replace(claimed_question(), answering_run_id=None)


def test_get_question_is_none_for_an_unknown_key(store: Store) -> None:
    with store.read() as transaction:
        assert get_question(transaction, KEY) is None
        assert latest_question(transaction, KEY.run_id) is None


def test_latest_question_is_the_one_claimed_last(store: Store) -> None:
    earlier = QuestionKey(KEY.run_id, "2026-11-10T09:00:00+00:00")
    with store.write() as transaction:
        insert_question(
            transaction, claimed_question(KEY, answering_run_id="a-1"), now=NOW
        )
        insert_question(
            transaction,
            claimed_question(earlier, answering_run_id="a-2"),
            now=NOW - timedelta(hours=2),
        )

    with store.read() as transaction:
        latest = latest_question(transaction, KEY.run_id)

    assert latest is not None
    assert latest.key == KEY


def test_any_answering_run_id_is_true_only_for_a_known_claim(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)

    with store.read() as transaction:
        assert any_answering_run_id(transaction, ANSWERING_RUN)
        assert not any_answering_run_id(transaction, "run-1")


def test_the_second_insert_loses_and_leaves_the_first_row(store: Store) -> None:
    with store.write() as transaction:
        assert insert_question(transaction, claimed_question(), now=NOW)
    with store.write() as transaction:
        second = claimed_question(answering_run_id=OTHER_RUN)
        assert not insert_question(transaction, second, now=NOW)

    with store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    assert record.answering_run_id == ANSWERING_RUN


def test_settle_waiting_moves_only_the_claim_it_holds(store: Store) -> None:
    evidence = AnsweringEvidence(proposed_answer="300", verdict="no", reason="r")
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)

    with store.write() as transaction:
        wrong_claim = settle_waiting(
            transaction,
            KEY,
            OTHER_RUN,
            reason=DeclineReason.CHECK_SAID_NO,
            detail=None,
            evidence=None,
            now=NOW,
        )
        right_claim = settle_waiting(
            transaction,
            KEY,
            ANSWERING_RUN,
            reason=DeclineReason.CHECK_SAID_NO,
            detail="no",
            evidence=evidence,
            now=NOW,
        )
        already_moved = settle_waiting(
            transaction,
            KEY,
            ANSWERING_RUN,
            reason=DeclineReason.CHECK_SAID_NO,
            detail=None,
            evidence=None,
            now=NOW,
        )

    assert (wrong_claim, right_claim, already_moved) == (False, True, False)
    with store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    assert record.state is QuestionState.WAITING_ON_PM
    assert record.waiting_reason is DeclineReason.CHECK_SAID_NO
    assert record.waiting_detail == "no"
    assert record.evidence == evidence


def test_replace_claim_swaps_run_and_passages_only_from_the_old_claim(
    store: Store,
) -> None:
    new_passage = replace(PASSAGE, id="r2")
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)

    with store.write() as transaction:
        wrong_old = replace_claim(
            transaction,
            KEY,
            old_answering_run_id=OTHER_RUN,
            new_answering_run_id="n-1",
            passages=(new_passage,),
            now=NOW,
        )
        swapped = replace_claim(
            transaction,
            KEY,
            old_answering_run_id=ANSWERING_RUN,
            new_answering_run_id="n-1",
            passages=(new_passage,),
            now=NOW,
        )

    assert (wrong_old, swapped) == (False, True)
    with store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    assert record.answering_run_id == "n-1"
    assert record.passages == (new_passage,)


def test_replace_claim_fails_once_the_question_left_claimed(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)

    with store.write() as transaction:
        assert not replace_claim(
            transaction,
            KEY,
            old_answering_run_id=ANSWERING_RUN,
            new_answering_run_id="n-1",
            passages=(),
            now=NOW,
        )
