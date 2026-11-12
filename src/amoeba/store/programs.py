"""Program, member and dependency-pair reads and upserts (slice 222, D3, D7).

Every function takes an open transaction (``Store.read()`` or ``Store.write()``).
An upsert writes, and moves ``updated_at``, only when a stored value changes, and
says whether it did. The clock is passed in so a test controls it. A list field given
to an upsert replaces the stored list whole. A member is removed softly (228 D8): its
row stays, ``removed_at`` is set, and every read here but ``get_member_any`` skips it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from amoeba.store import sql
from amoeba.store.errors import StoreIntegrityError
from amoeba.store.models import DependencyPair, Member, MemberSettings, Program
from amoeba.store.row_values import (
    decode_string_list,
    decode_timestamp,
    encode_string_list,
    encode_timestamp,
    optional_text,
    optional_timestamp,
    text,
    vocabulary,
)
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ConsumedMode

# --- row mapping: positional, in the column order of the sql.py SELECTs -----


def _program(row: Sequence[object]) -> Program:
    return Program(
        program_id=text(row[0], "programs.program_id"),
        concept_member=optional_text(row[1], "programs.concept_member"),
        concept_path=optional_text(row[2], "programs.concept_path"),
        registered_at=decode_timestamp(row[3], "programs.registered_at"),
        updated_at=decode_timestamp(row[4], "programs.updated_at"),
    )


def _member(row: Sequence[object]) -> Member:
    return Member(
        program_id=text(row[1], "members.program_id"),
        settings=MemberSettings(
            project_id=text(row[0], "members.project_id"),
            rules_paths=decode_string_list(row[2], "members.rules_paths"),
            authorize_allow=decode_string_list(row[3], "members.authorize_allow"),
            authorize_deny=decode_string_list(row[4], "members.authorize_deny"),
        ),
        registered_at=decode_timestamp(row[5], "members.registered_at"),
        updated_at=decode_timestamp(row[6], "members.updated_at"),
        removed_at=optional_timestamp(row[7], "members.removed_at"),
    )


def _pair(row: Sequence[object]) -> DependencyPair:
    return DependencyPair(
        program_id=text(row[0], "dependency_pairs.program_id"),
        provider_id=text(row[1], "dependency_pairs.provider_id"),
        consumer_id=text(row[2], "dependency_pairs.consumer_id"),
        consumed=vocabulary(row[3], ConsumedMode, "dependency_pairs.consumed"),
        registered_at=decode_timestamp(row[4], "dependency_pairs.registered_at"),
        updated_at=decode_timestamp(row[5], "dependency_pairs.updated_at"),
    )


# --- reads ------------------------------------------------------------------


def list_programs(transaction: Transaction) -> tuple[Program, ...]:
    """Every program, by id."""
    rows = transaction.execute(sql.SELECT_PROGRAMS).fetchall()
    return tuple(_program(row) for row in rows)


def get_program(transaction: Transaction, program_id: str) -> Program | None:
    row = transaction.execute(sql.SELECT_PROGRAM, (program_id,)).fetchone()
    return None if row is None else _program(row)


def get_member(transaction: Transaction, project_id: str) -> Member | None:
    row = transaction.execute(sql.SELECT_MEMBER, (project_id,)).fetchone()
    return None if row is None else _member(row)


def get_member_any(transaction: Transaction, project_id: str) -> Member | None:
    """The member row whether or not it was removed (``removed_at`` says which)."""
    row = transaction.execute(sql.SELECT_MEMBER_ANY, (project_id,)).fetchone()
    return None if row is None else _member(row)


def members_of(transaction: Transaction, program_id: str) -> tuple[Member, ...]:
    rows = transaction.execute(sql.SELECT_MEMBERS_OF, (program_id,)).fetchall()
    return tuple(_member(row) for row in rows)


def member_settings(transaction: Transaction, project_id: str) -> MemberSettings | None:
    member = get_member(transaction, project_id)
    return None if member is None else member.settings


def pairs_of(transaction: Transaction, program_id: str) -> tuple[DependencyPair, ...]:
    rows = transaction.execute(sql.SELECT_PAIRS_OF, (program_id,)).fetchall()
    return tuple(_pair(row) for row in rows)


def get_pair(
    transaction: Transaction, provider_id: str, consumer_id: str
) -> DependencyPair | None:
    row = transaction.execute(sql.SELECT_PAIR, (provider_id, consumer_id)).fetchone()
    return None if row is None else _pair(row)


# --- upserts: each returns whether it wrote ----------------------------------


def upsert_program(
    transaction: Transaction,
    *,
    program_id: str,
    concept_member: str | None,
    concept_path: str | None,
    now: datetime,
) -> bool:
    """Create the program or set its concept pair; both null or both set."""
    stamp = encode_timestamp(now)
    existing = get_program(transaction, program_id)
    if existing is None:
        transaction.execute(
            sql.INSERT_PROGRAM,
            (program_id, concept_member, concept_path, stamp, stamp),
        )
        return True
    if (existing.concept_member, existing.concept_path) == (
        concept_member,
        concept_path,
    ):
        return False
    transaction.execute(
        sql.UPDATE_PROGRAM, (concept_member, concept_path, stamp, program_id)
    )
    return True


def upsert_member(
    transaction: Transaction,
    *,
    program_id: str,
    settings: MemberSettings,
    now: datetime,
) -> bool:
    """Create the member or replace its lists.

    A removed member is registered afresh, in this program, whichever it was in.

    Raises:
        StoreIntegrityError: The active member already belongs to another program.
    """
    stamp = encode_timestamp(now)
    lists = (
        encode_string_list(settings.rules_paths),
        encode_string_list(settings.authorize_allow),
        encode_string_list(settings.authorize_deny),
    )
    existing = get_member_any(transaction, settings.project_id)
    if existing is None:
        transaction.execute(
            sql.INSERT_MEMBER,
            (settings.project_id, program_id, *lists, stamp, stamp),
        )
        return True
    if existing.removed_at is not None:
        transaction.execute(
            sql.REREGISTER_MEMBER,
            (program_id, *lists, stamp, stamp, settings.project_id),
        )
        return True
    if existing.program_id != program_id:
        raise StoreIntegrityError(
            f"member {settings.project_id!r} belongs to program "
            f"{existing.program_id!r}, not {program_id!r}"
        )
    if existing.settings == settings:
        return False
    transaction.execute(sql.UPDATE_MEMBER, (*lists, stamp, settings.project_id))
    return True


def upsert_pair(
    transaction: Transaction,
    *,
    program_id: str,
    provider_id: str,
    consumer_id: str,
    consumed: ConsumedMode,
    now: datetime,
) -> bool:
    """Create the pair or set its ``consumed``."""
    stamp = encode_timestamp(now)
    existing = get_pair(transaction, provider_id, consumer_id)
    if existing is None:
        transaction.execute(
            sql.INSERT_PAIR,
            (program_id, provider_id, consumer_id, consumed.value, stamp, stamp),
        )
        return True
    if existing.consumed is consumed:
        return False
    transaction.execute(
        sql.UPDATE_PAIR, (consumed.value, stamp, provider_id, consumer_id)
    )
    return True


# --- removal (228 D8) ----------------------------------------------------------


def remove_member(transaction: Transaction, project_id: str, now: datetime) -> bool:
    """Soft-remove the member and delete its pairs; False if it was not active.

    The member's question, answer and release rows stay: they are the record.
    """
    stamp = encode_timestamp(now)
    cursor = transaction.execute(sql.REMOVE_MEMBER, (stamp, stamp, project_id))
    if cursor.rowcount != 1:
        return False
    transaction.execute(sql.DELETE_PAIRS_OF_MEMBER, (project_id, project_id))
    return True


def remove_pair(transaction: Transaction, provider_id: str, consumer_id: str) -> bool:
    """Delete the pair; False if there was none."""
    cursor = transaction.execute(sql.DELETE_PAIR, (provider_id, consumer_id))
    return cursor.rowcount == 1
