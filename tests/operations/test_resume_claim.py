"""``claim_resume`` and ``record_resume``'s claim id, one test per row of D6
(slice 262)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.question_support import KEY, NOW, seed_members, waiting_question
from store_open import open_local_store

from amoeba.operations.steps.resume import (
    ResumeClaimed,
    ResumeFinal,
    ResumeInFlight,
    claim_resume,
)
from amoeba.store.answers import add_pm_answer, get_answer, record_resume
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ResumeOutcome

LIMIT_SECONDS = 216.5
LIMIT = timedelta(seconds=LIMIT_SECONDS)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        with opened.write() as transaction:
            insert_question(transaction, waiting_question(KEY), now=NOW)
        yield opened


def _answer(store: Store) -> int:
    with store.write() as transaction:
        return add_pm_answer(transaction, KEY, "an answer", now=NOW, via=None)


def _claim(store: Store, seq: int, after: timedelta = timedelta(0)):
    with store.write() as transaction:
        return claim_resume(transaction, seq, NOW + after, LIMIT_SECONDS)


def _record(store: Store, seq: int, outcome: ResumeOutcome, claim_id: str | None):
    with store.write() as transaction:
        return record_resume(
            transaction,
            seq,
            outcome,
            detail=None,
            log=None,
            at=NOW,
            claim_id=claim_id,
        )


def _held(store: Store, seq: int) -> tuple[str | None, ResumeOutcome | None]:
    with store.read() as transaction:
        answer = get_answer(transaction, seq)
    assert answer is not None
    return answer.resume_claim_id, answer.resume_outcome


def test_a_free_claim_is_taken_and_stamped(store: Store) -> None:
    seq = _answer(store)

    claim = _claim(store, seq)

    assert isinstance(claim, ResumeClaimed)
    assert _held(store, seq) == (claim.claim_id, None)
    with store.read() as transaction:
        answer = get_answer(transaction, seq)
    assert answer is not None
    assert answer.resume_started_at == NOW


def test_a_claim_in_flight_is_refused(store: Store) -> None:
    seq = _answer(store)
    first = _claim(store, seq)

    second = _claim(store, seq, LIMIT - timedelta(seconds=1))

    assert isinstance(first, ResumeClaimed)
    assert second == ResumeInFlight()
    assert _held(store, seq)[0] == first.claim_id


def test_a_claim_is_retaken_once_it_is_the_limit_old_and_not_one_second_before(
    store: Store,
) -> None:
    seq = _answer(store)
    first = _claim(store, seq)
    assert isinstance(first, ResumeClaimed)

    assert _claim(store, seq, LIMIT - timedelta(seconds=1)) == ResumeInFlight()
    retaken = _claim(store, seq, LIMIT)

    assert isinstance(retaken, ResumeClaimed)
    assert retaken.claim_id != first.claim_id
    assert _held(store, seq)[0] == retaken.claim_id


@pytest.mark.parametrize("final", [ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED])
def test_a_final_outcome_is_never_claimed(store: Store, final: ResumeOutcome) -> None:
    seq = _answer(store)
    claim = _claim(store, seq)
    assert isinstance(claim, ResumeClaimed)
    _record(store, seq, final, claim.claim_id)

    assert _claim(store, seq) == ResumeFinal(final)
    assert _claim(store, seq, LIMIT * 10) == ResumeFinal(final)


def test_a_refused_outcome_is_claimable(store: Store) -> None:
    seq = _answer(store)
    first = _claim(store, seq)
    assert isinstance(first, ResumeClaimed)
    _record(store, seq, ResumeOutcome.REFUSED, first.claim_id)

    assert isinstance(_claim(store, seq), ResumeClaimed)


def test_an_outcome_clears_the_claim_only_when_it_is_the_callers(
    store: Store,
) -> None:
    seq = _answer(store)
    first = _claim(store, seq)
    assert isinstance(first, ResumeClaimed)

    _record(store, seq, ResumeOutcome.REFUSED, None)  # clears nothing
    assert _held(store, seq) == (first.claim_id, ResumeOutcome.REFUSED)
    _record(store, seq, ResumeOutcome.REFUSED, "someone-elses")
    assert _held(store, seq)[0] == first.claim_id
    _record(store, seq, ResumeOutcome.REFUSED, first.claim_id)

    assert _held(store, seq) == (None, ResumeOutcome.REFUSED)


def test_a_late_outcome_from_a_claim_that_ran_out_does_not_clear_the_newer_claim(
    store: Store,
) -> None:
    seq = _answer(store)
    old = _claim(store, seq)
    newer = _claim(store, seq, LIMIT)
    assert isinstance(old, ResumeClaimed)
    assert isinstance(newer, ResumeClaimed)

    wrote = _record(store, seq, ResumeOutcome.REFUSED, old.claim_id)

    assert wrote
    assert _held(store, seq) == (newer.claim_id, ResumeOutcome.REFUSED)
    # The newer claim is still in flight, and a refused outcome does not release it.
    assert _claim(store, seq, LIMIT + timedelta(seconds=1)) == ResumeInFlight()


def test_three_threads_claim_one_answer_at_once_and_one_wins(tmp_path: Path) -> None:
    path = tmp_path / "amoeba.sqlite3"
    with open_local_store(path) as first:
        seed_members(first)
        with first.write() as transaction:
            insert_question(transaction, waiting_question(KEY), now=NOW)
        seq = _answer(first)
    barrier = threading.Barrier(3)
    results: list[object] = []

    def claim() -> None:
        with open_local_store(path) as mine:
            barrier.wait()
            results.append(_claim(mine, seq))

    threads = [threading.Thread(target=claim) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    winners = [result for result in results if isinstance(result, ResumeClaimed)]
    assert len(results) == 3
    assert len(winners) == 1
    assert results.count(ResumeInFlight()) == 2
