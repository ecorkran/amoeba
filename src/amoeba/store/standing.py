"""Standing answers: give, withdraw, list, the ones reaching a member (slice 230).

Every function takes the caller's ``Transaction``; a writer also takes ``now``. Nothing
here reads a clock or the config, and nothing reads ``members`` (228 D8): the caller
passes the member's ids.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum

from amoeba.store import sql_standing
from amoeba.store.models import StandingAnswerRow
from amoeba.store.row_values import (
    decode_timestamp,
    encode_timestamp,
    integer,
    optional_text,
    optional_timestamp,
    text,
    vocabulary,
)
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import MEMBER_REMOVED_REASON, StandingReach


class StandingWithdrawal(StrEnum):
    """What ``withdraw_standing`` found; the operation maps these to its outcome."""

    WITHDRAWN = "withdrawn"
    ALREADY_WITHDRAWN = "already_withdrawn"
    NOT_FOUND = "not_found"


def _row(row: Sequence[object]) -> StandingAnswerRow:
    return StandingAnswerRow(
        standing_id=integer(row[0], "standing_answers.id"),
        text=text(row[1], "standing_answers.text"),
        reach=vocabulary(row[2], StandingReach, "standing_answers.reach"),
        program_id=optional_text(row[3], "standing_answers.program_id"),
        member_id=optional_text(row[4], "standing_answers.member_id"),
        given_at=decode_timestamp(row[5], "standing_answers.given_at"),
        withdrawn_at=optional_timestamp(row[6], "standing_answers.withdrawn_at"),
        withdraw_reason=optional_text(row[7], "standing_answers.withdraw_reason"),
    )


def give_standing(
    transaction: Transaction,
    ruling: str,
    reach: StandingReach,
    program_id: str | None,
    member_id: str | None,
    now: datetime,
) -> tuple[int, bool]:
    """The id of the active row with this ruling text and reach, and whether it is new.

    A matching active row is returned with ``False`` and nothing is written (D2's safe
    repeat); otherwise a row is inserted. The caller holds one write transaction for
    both, so two calls never insert twice.
    """
    match = transaction.execute(
        sql_standing.SELECT_ACTIVE_MATCH, (ruling, reach.value, program_id, member_id)
    ).fetchone()
    if match is not None:
        return integer(match[0], "standing_answers.id"), False
    cursor = transaction.execute(
        sql_standing.INSERT_STANDING,
        (ruling, reach.value, program_id, member_id, encode_timestamp(now)),
    )
    return integer(cursor.lastrowid, "standing_answers.id"), True


def withdraw_standing(
    transaction: Transaction, standing_id: int, reason: str, now: datetime
) -> StandingWithdrawal:
    """Withdraw an active row; a withdrawn or unknown one is left as it is (D3)."""
    cursor = transaction.execute(
        sql_standing.WITHDRAW_STANDING, (encode_timestamp(now), reason, standing_id)
    )
    if cursor.rowcount == 1:
        return StandingWithdrawal.WITHDRAWN
    found = transaction.execute(
        sql_standing.SELECT_WITHDRAWN_AT, (standing_id,)
    ).fetchone()
    if found is None:
        return StandingWithdrawal.NOT_FOUND
    return StandingWithdrawal.ALREADY_WITHDRAWN


def list_standing(
    transaction: Transaction, *, include_withdrawn: bool
) -> tuple[StandingAnswerRow, ...]:
    """Newest first by ``given_at``, then id; withdrawn rows only when asked for."""
    statement = (
        sql_standing.SELECT_ALL_STANDING
        if include_withdrawn
        else sql_standing.SELECT_ACTIVE_STANDING
    )
    return tuple(_row(row) for row in transaction.execute(statement))


def standing_reaching(
    transaction: Transaction, project_id: str, program_id: str
) -> tuple[StandingAnswerRow, ...]:
    """The active rows that reach this member, in id order (D5)."""
    rows = transaction.execute(
        sql_standing.SELECT_STANDING_REACHING,
        (
            StandingReach.ALL.value,
            StandingReach.PROGRAM.value,
            program_id,
            StandingReach.MEMBER.value,
            project_id,
        ),
    )
    return tuple(_row(row) for row in rows)


def withdraw_member_standing(
    transaction: Transaction, project_id: str, now: datetime
) -> int:
    """Withdraw a removed member's member-reach rows; returns how many (D8)."""
    cursor = transaction.execute(
        sql_standing.WITHDRAW_MEMBER_STANDING,
        (
            encode_timestamp(now),
            MEMBER_REMOVED_REASON,
            StandingReach.MEMBER.value,
            project_id,
        ),
    )
    return cursor.rowcount
