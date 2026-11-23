"""``withdraw``: take back a standing answer, safely repeated (slice 230, D3, D10)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.operations.cf_readers import cf_member_resolver
from amoeba.operations.standing import standing
from amoeba.operations.standing_models import (
    WithdrawOutcome,
    WithdrawRejection,
)
from amoeba.operations.withdraw import withdraw
from amoeba.store.standing import list_standing
from amoeba.store.store import Store
from operations.standing_support import MAX_CHARS, NOW, RecordingCf, seeded_store

LATER = NOW + timedelta(hours=1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from seeded_store(tmp_path / "amoeba.sqlite3")


@pytest.fixture
def standing_id(store: Store) -> int:
    given = standing(
        store,
        {"text": "rule"},
        max_chars=MAX_CHARS,
        resolve_member=cf_member_resolver(RecordingCf()),
        now=NOW,
    )
    assert given.standing_id is not None
    return given.standing_id


def _row_fields(store: Store) -> tuple[object, ...]:
    with store.read() as transaction:
        (row,) = list_standing(transaction, include_withdrawn=True)
    return (row.withdrawn_at, row.withdraw_reason)


def test_withdraw_records_the_time_and_reason(store: Store, standing_id: int) -> None:
    result = withdraw(store, {"standing_id": standing_id, "reason": "wrong"}, now=LATER)

    assert (result.outcome, result.standing_id) == (
        WithdrawOutcome.WITHDRAWN,
        standing_id,
    )
    assert _row_fields(store) == (LATER, "wrong")
    with store.read() as transaction:
        assert list_standing(transaction, include_withdrawn=False) == ()


def test_a_second_withdraw_is_unchanged(store: Store, standing_id: int) -> None:
    withdraw(store, {"standing_id": standing_id, "reason": "wrong"}, now=LATER)

    again = withdraw(
        store,
        {"standing_id": standing_id, "reason": "other"},
        now=LATER + timedelta(minutes=1),
    )

    assert (again.outcome, again.standing_id) == (
        WithdrawOutcome.UNCHANGED,
        standing_id,
    )
    assert _row_fields(store) == (LATER, "wrong")


def test_an_unknown_id_is_rejected(store: Store, standing_id: int) -> None:
    result = withdraw(store, {"standing_id": standing_id + 1, "reason": "x"}, now=LATER)

    assert (result.outcome, result.rejection) == (
        WithdrawOutcome.REJECTED,
        WithdrawRejection.NO_SUCH_STANDING_ANSWER,
    )
    assert _row_fields(store) == (None, None)


@pytest.mark.parametrize(
    "document",
    [
        {"standing_id": 0, "reason": "x"},
        {"standing_id": -1, "reason": "x"},
        {"standing_id": "1", "reason": "x"},
        {"standing_id": 1.5, "reason": "x"},
        {"standing_id": 1, "reason": "  "},
        {"standing_id": 1},
    ],
)
def test_a_bad_document_is_malformed(
    store: Store, standing_id: int, document: dict[str, object]
) -> None:
    result = withdraw(store, document, now=LATER)

    assert (result.outcome, result.rejection) == (
        WithdrawOutcome.REJECTED,
        WithdrawRejection.MALFORMED,
    )
    assert result.problems
    assert _row_fields(store) == (None, None)


def test_a_committed_withdraw_whose_result_is_dropped_repeats_as_unchanged(
    store: Store, standing_id: int
) -> None:
    document = {"standing_id": standing_id, "reason": "wrong"}
    withdraw(store, document, now=LATER)  # committed; the result was lost (D10)

    repeated = withdraw(store, document, now=LATER)

    assert (repeated.outcome, repeated.standing_id) == (
        WithdrawOutcome.UNCHANGED,
        standing_id,
    )
    assert _row_fields(store) == (LATER, "wrong")
