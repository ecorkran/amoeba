"""Insert rows straight through the store's SQL constants, to seed any state.

Every column value is an argument and none has a default, so a test states the whole
row. Seeding bypasses ``set_up`` and the operations on purpose: a test of one
operation builds its starting state without going through another. Each function
takes the open ``Store.write()`` transaction.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from amoeba.answering.values import AnsweredBy
from amoeba.store import sql
from amoeba.store.checkouts import insert_checkout as store_insert_checkout
from amoeba.store.messages import insert_request
from amoeba.store.row_values import encode_string_list, encode_timestamp
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import (
    ConsumedMode,
    QuestionState,
    ResumeOutcome,
    RulesFrom,
)


def insert_program(
    transaction: Transaction,
    *,
    program_id: str,
    concept_member: str | None,
    concept_path: str | None,
    registered_at: datetime,
    updated_at: datetime,
) -> None:
    transaction.execute(
        sql.INSERT_PROGRAM,
        (
            program_id,
            concept_member,
            concept_path,
            encode_timestamp(registered_at),
            encode_timestamp(updated_at),
            transaction.acting("programs").owner_id,
        ),
    )


def insert_member(
    transaction: Transaction,
    *,
    project_id: str,
    program_id: str,
    rules_paths: tuple[str, ...],
    authorize_allow: tuple[str, ...],
    authorize_deny: tuple[str, ...],
    registered_at: datetime,
    updated_at: datetime,
    rules_from: RulesFrom = RulesFrom.NAMED,
    name: str | None = None,
    origin: str | None = None,
) -> None:
    """Insert a member; with no ``name`` it is named by its id (naming's rule for a
    member Context Forge does not know)."""
    transaction.execute(
        sql.INSERT_MEMBER,
        (
            project_id,
            program_id,
            encode_string_list(rules_paths),
            encode_string_list(authorize_allow),
            encode_string_list(authorize_deny),
            encode_timestamp(registered_at),
            encode_timestamp(updated_at),
            rules_from,
            project_id if name is None else name,
            origin,
            transaction.acting("members").owner_id,
        ),
    )


def insert_checkout(
    transaction: Transaction,
    *,
    member_id: str,
    cf_project_id: str,
    path: str,
    wake_command: str | None = None,
    now: datetime,
) -> None:
    """Add a checkout on the acting machine; ``now`` is the row's ``added_at``."""
    store_insert_checkout(
        transaction,
        member_id=member_id,
        cf_project_id=cf_project_id,
        path=path,
        wake_command=wake_command,
        now=now,
    )


def insert_pair(
    transaction: Transaction,
    *,
    program_id: str,
    provider_id: str,
    consumer_id: str,
    consumed: ConsumedMode,
    registered_at: datetime,
    updated_at: datetime,
) -> None:
    transaction.execute(
        sql.INSERT_PAIR,
        (
            program_id,
            provider_id,
            consumer_id,
            consumed.value,
            encode_timestamp(registered_at),
            encode_timestamp(updated_at),
            transaction.acting("dependency_pairs").owner_id,
        ),
    )


def insert_question(
    transaction: Transaction,
    *,
    run_id: str,
    paused_at: str,
    member_id: str,
    question: str,
    checkout: str,
    state: QuestionState,
    answering_run_id: str | None,
    waiting_reason: str | None,
    claimed_at: datetime,
    updated_at: datetime,
) -> None:
    acting = transaction.acting("questions")
    transaction.execute(
        sql.INSERT_QUESTION,
        (
            run_id,
            paused_at,
            member_id,
            question,
            checkout,
            state.value,
            answering_run_id,
            waiting_reason,
            encode_timestamp(claimed_at),
            encode_timestamp(updated_at),
            acting.owner_id,
            acting.machine_id,
        ),
    )


def insert_answer(
    transaction: Transaction,
    *,
    run_id: str,
    paused_at: str,
    answered_by: AnsweredBy,
    answer: str,
    recorded_at: datetime,
    resume_outcome: ResumeOutcome | None,
) -> None:
    transaction.execute(
        sql.INSERT_ANSWER,
        (
            run_id,
            paused_at,
            answered_by.value,
            answer,
            encode_timestamp(recorded_at),
            None if resume_outcome is None else resume_outcome.value,
            transaction.acting("answers").owner_id,
        ),
    )


#: Long enough that a seeded request is never past its expiry in a test.
SEEDED_REQUEST_TTL = timedelta(days=3650)


def mark_wake_wanted(transaction: Transaction, member_id: str, at: datetime) -> str:
    """An open request to ``member_id`` whose ``wake_wanted_at`` is ``at``: the
    member has a wake due (262 D8, rule 1) as ``send`` would have marked it.

    The request is from the member to itself, so no other member needs seeding. It is
    never expired, and its id is numbered, so a test may seed several marks. Returns
    the request's id.
    """
    taken = transaction.execute(
        "SELECT COUNT(*) FROM messages WHERE message_id LIKE 'wake-mark-%'"
    ).fetchone()
    message_id = f"wake-mark-{taken[0] if taken else 0}-{member_id}"
    insert_request(
        transaction,
        message_id=message_id,
        from_member=member_id,
        to_member=member_id,
        parent_id=None,
        parent_depth=None,
        subject="seeded request",
        body="seeded request",
        ttl=SEEDED_REQUEST_TTL,
        now=at,
    )
    transaction.execute(
        "UPDATE messages SET wake_wanted_at = ? WHERE message_id = ?",
        (encode_timestamp(at), message_id),
    )
    return message_id
