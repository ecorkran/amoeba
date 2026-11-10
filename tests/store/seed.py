"""Insert rows straight through the store's SQL constants, to seed any state.

Every column value is an argument and none has a default, so a test states the whole
row. Seeding bypasses ``set_up`` and the operations on purpose: a test of one
operation builds its starting state without going through another. Each function
takes the open ``Store.write()`` transaction.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.answering.values import AnsweredBy
from amoeba.store import sql
from amoeba.store.row_values import encode_string_list, encode_timestamp
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ConsumedMode, QuestionState, ResumeOutcome


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
) -> None:
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
        ),
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
        ),
    )
