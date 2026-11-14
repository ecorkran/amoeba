"""Release reports: the writers behind ``report_release`` and the read behind
``changes`` (slice 227, D2, D3).

Every function takes the caller's open transaction. A duplicate ``(member, commit)``
insert is a caller bug and raises ``StoreIntegrityError``; nothing here catches it.
Times are the store's UTC text, written with ``encode_timestamp``.
"""

from __future__ import annotations

from datetime import datetime
from typing import assert_never

from amoeba.store import sql
from amoeba.store.models import Release
from amoeba.store.row_values import (
    decode_string_list,
    decode_timestamp,
    encode_string_list,
    encode_timestamp,
    integer,
    optional_text,
    optional_timestamp,
    text,
)
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ConsumedMode


def _release(row: tuple[object, ...]) -> Release:
    return Release(
        seq=integer(row[0], "releases.seq"),
        commit=text(row[1], "releases.commit_sha"),
        version=optional_text(row[2], "releases.version"),
        changed=text(row[3], "releases.changed"),
        touched=decode_string_list(row[4], "releases.touched"),
        reported_at=decode_timestamp(row[5], "releases.reported_at"),
        versioned_at=optional_timestamp(row[6], "releases.versioned_at"),
    )


def release_for_commit(
    transaction: Transaction, member_id: str, commit: str
) -> Release | None:
    """The member's report for ``commit``, or ``None``."""
    row = transaction.execute(
        sql.SELECT_RELEASE_FOR_COMMIT, (member_id, commit)
    ).fetchone()
    return None if row is None else _release(row)


def insert_release(
    transaction: Transaction,
    member_id: str,
    commit: str,
    version: str | None,
    changed: str,
    touched: tuple[str, ...],
    now: datetime,
) -> None:
    """A new report; ``versioned_at`` is ``now`` only when a version is given."""
    stamp = encode_timestamp(now)
    transaction.execute(
        sql.INSERT_RELEASE,
        (
            member_id,
            commit,
            version,
            changed,
            encode_string_list(touched),
            stamp,
            None if version is None else stamp,
        ),
    )


def add_version(
    transaction: Transaction,
    member_id: str,
    commit: str,
    version: str,
    changed: str,
    touched: tuple[str, ...],
    now: datetime,
) -> None:
    """Set the version and replace the text; ``reported_at`` and ``seq`` stay."""
    transaction.execute(
        sql.VERSION_RELEASE,
        (
            version,
            encode_timestamp(now),
            changed,
            encode_string_list(touched),
            member_id,
            commit,
        ),
    )


def correct_release(
    transaction: Transaction,
    member_id: str,
    commit: str,
    version: str | None,
    changed: str,
    touched: tuple[str, ...],
    now: datetime,
) -> None:
    """Replace the text and move the times to ``now``; a given version replaces the
    stored one, otherwise the stored one is kept."""
    stamp = encode_timestamp(now)
    transaction.execute(
        sql.CORRECT_RELEASE,
        (
            changed,
            encode_string_list(touched),
            version,
            stamp,
            version,
            stamp,
            member_id,
            commit,
        ),
    )


def delete_release(transaction: Transaction, member_id: str, commit: str) -> bool:
    """Remove the report; whether there was one."""
    cursor = transaction.execute(sql.DELETE_RELEASE, (member_id, commit))
    return cursor.rowcount > 0


def visible_releases(
    transaction: Transaction,
    provider_id: str,
    consumed: ConsumedMode,
    since: str,
) -> tuple[Release, ...]:
    """The provider's reports a consumer of this mode sees at or after ``since``
    (the store's UTC text), oldest first."""
    match consumed:
        case ConsumedMode.FROM_SOURCE:
            statement = sql.SELECT_RELEASES_FROM_SOURCE
        case ConsumedMode.FROM_RELEASE:
            statement = sql.SELECT_RELEASES_FROM_RELEASE
        case _:
            assert_never(consumed)
    rows = transaction.execute(statement, (provider_id, since)).fetchall()
    return tuple(_release(row) for row in rows)
