"""The standing answers store (slice 230, D1 to D5, D8), against a throwaway store."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amoeba.store.standing import (
    StandingWithdrawal,
    give_standing,
    list_standing,
    standing_reaching,
    withdraw_member_standing,
    withdraw_standing,
)
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import MEMBER_REMOVED_REASON, StandingReach
from store.seed import insert_member, insert_program

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
#: Program to its members.
LAYOUT = {"alpha": ("a1", "a2"), "beta": ("b1",)}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            for program_id, members in LAYOUT.items():
                insert_program(
                    transaction,
                    program_id=program_id,
                    concept_member=None,
                    concept_path=None,
                    registered_at=NOW,
                    updated_at=NOW,
                )
                for member in members:
                    insert_member(
                        transaction,
                        project_id=member,
                        program_id=program_id,
                        rules_paths=(),
                        authorize_allow=(),
                        authorize_deny=(),
                        registered_at=NOW,
                        updated_at=NOW,
                    )
        yield opened


def _give(
    transaction: Transaction,
    text: str = "rule",
    reach: StandingReach = StandingReach.ALL,
    program_id: str | None = None,
    member_id: str | None = None,
    now: datetime = NOW,
) -> tuple[int, bool]:
    return give_standing(transaction, text, reach, program_id, member_id, now)


def test_give_inserts_a_row(store: Store) -> None:
    with store.write() as transaction:
        standing_id, created = _give(transaction)

    with store.read() as transaction:
        (row,) = list_standing(transaction, include_withdrawn=True)
    assert created
    assert (row.standing_id, row.text, row.reach, row.given_at) == (
        standing_id,
        "rule",
        StandingReach.ALL,
        NOW,
    )
    assert (row.program_id, row.member_id, row.withdrawn_at) == (None, None, None)


@pytest.mark.parametrize(
    ("reach", "program_id", "member_id"),
    [
        (StandingReach.ALL, None, None),
        (StandingReach.PROGRAM, "alpha", None),
        (StandingReach.MEMBER, None, "a1"),
    ],
)
def test_the_same_give_again_returns_the_same_id(
    store: Store, reach: StandingReach, program_id: str | None, member_id: str | None
) -> None:
    with store.write() as transaction:
        first, _ = _give(transaction, "r", reach, program_id, member_id)
    with store.write() as transaction:
        second, created = _give(transaction, "r", reach, program_id, member_id, LATER)

    with store.read() as transaction:
        rows = list_standing(transaction, include_withdrawn=True)
    assert (second, created) == (first, False)
    assert len(rows) == 1


@pytest.mark.parametrize(
    ("text", "reach", "program_id", "member_id"),
    [
        ("rule.", StandingReach.PROGRAM, "alpha", None),
        ("rule", StandingReach.ALL, None, None),
        ("rule", StandingReach.PROGRAM, "beta", None),
        ("rule", StandingReach.MEMBER, None, "a2"),
    ],
)
def test_any_difference_is_a_new_row(
    store: Store,
    text: str,
    reach: StandingReach,
    program_id: str | None,
    member_id: str | None,
) -> None:
    with store.write() as transaction:
        existing, _ = _give(transaction, "rule", StandingReach.PROGRAM, "alpha", None)
        _give(transaction, "rule", StandingReach.MEMBER, None, "a1")
        standing_id, created = _give(transaction, text, reach, program_id, member_id)
        rows = list_standing(transaction, include_withdrawn=True)

    assert created
    assert standing_id != existing
    assert len(rows) == 3


def test_a_give_after_the_match_is_withdrawn_is_a_new_row(store: Store) -> None:
    with store.write() as transaction:
        first, _ = _give(transaction)
        withdraw_standing(transaction, first, "wrong", NOW)
        second, created = _give(transaction, now=LATER)

    assert created
    assert second != first


def test_withdraw_sets_both_fields_once(store: Store) -> None:
    with store.write() as transaction:
        standing_id, _ = _give(transaction)
        first = withdraw_standing(transaction, standing_id, "wrong", NOW)
        second = withdraw_standing(transaction, standing_id, "again", LATER)
        (row,) = list_standing(transaction, include_withdrawn=True)

    assert (first, second) == (
        StandingWithdrawal.WITHDRAWN,
        StandingWithdrawal.ALREADY_WITHDRAWN,
    )
    assert (row.withdrawn_at, row.withdraw_reason) == (NOW, "wrong")


def test_an_unknown_id_is_not_found(store: Store) -> None:
    with store.write() as transaction:
        found = withdraw_standing(transaction, 99, "why", NOW)

    assert found is StandingWithdrawal.NOT_FOUND


def test_list_is_newest_first_and_filters_withdrawn(store: Store) -> None:
    with store.write() as transaction:
        oldest, _ = _give(transaction, "one", now=NOW)
        same_time, _ = _give(transaction, "two", now=LATER)
        newest, _ = _give(transaction, "three", now=LATER)
        withdraw_standing(transaction, oldest, "old", LATER)
        active = list_standing(transaction, include_withdrawn=False)
        every = list_standing(transaction, include_withdrawn=True)

    assert [row.standing_id for row in active] == [newest, same_time]
    assert [row.standing_id for row in every] == [newest, same_time, oldest]


def test_standing_reaching_returns_exactly_the_rows_in_reach(store: Store) -> None:
    with store.write() as transaction:
        everyone, _ = _give(transaction, "all")
        alpha, _ = _give(transaction, "alpha", StandingReach.PROGRAM, "alpha")
        _give(transaction, "beta", StandingReach.PROGRAM, "beta")
        a1, _ = _give(transaction, "a1", StandingReach.MEMBER, None, "a1")
        _give(transaction, "a2", StandingReach.MEMBER, None, "a2")
        _give(transaction, "b1", StandingReach.MEMBER, None, "b1")
        gone, _ = _give(transaction, "gone", StandingReach.PROGRAM, "alpha")
        withdraw_standing(transaction, gone, "old", NOW)

    with store.read() as transaction:
        for_a1 = standing_reaching(transaction, "a1", "alpha")
        for_b1 = standing_reaching(transaction, "b1", "beta")

    assert [row.standing_id for row in for_a1] == [everyone, alpha, a1]
    assert [row.text for row in for_b1] == ["all", "beta", "b1"]


def test_withdraw_member_standing_withdraws_only_that_members_rows(
    store: Store,
) -> None:
    with store.write() as transaction:
        _give(transaction, "all")
        _give(transaction, "alpha", StandingReach.PROGRAM, "alpha")
        _give(transaction, "first", StandingReach.MEMBER, None, "a1")
        _give(transaction, "second", StandingReach.MEMBER, None, "a1")
        _give(transaction, "other", StandingReach.MEMBER, None, "a2")
        count = withdraw_member_standing(transaction, "a1", LATER)
        rows = list_standing(transaction, include_withdrawn=True)

    withdrawn = {row.text: row.withdraw_reason for row in rows if row.withdrawn_at}
    assert count == 2
    assert withdrawn == {
        "first": MEMBER_REMOVED_REASON,
        "second": MEMBER_REMOVED_REASON,
    }
