"""Shared setup for the question and answer store tests (slice 223)."""

from __future__ import annotations

from datetime import UTC, datetime

from amoeba.answering.values import DeclineReason, PassageRef
from amoeba.store.held_questions import HeldQuestion, insert_held
from amoeba.store.models import QuestionKey
from amoeba.store.questions import NewQuestion
from amoeba.store.store import Store, Transaction
from store.seed import insert_member, insert_program

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
MEMBER_ID = "member-a"
OTHER_MEMBER_ID = "member-b"
KEY = QuestionKey(run_id="run-1", paused_at="2026-11-10T11:00:00+00:00")
ANSWERING_RUN = "amoeba-20261110T110000Z-aaaaaaaaaaaa"
PASSAGE = PassageRef(id="r1", source="CLAUDE.md", question_id=None, date=NOW)


def seed_members(store: Store) -> None:
    """One program with two members, so a test can tell members apart."""
    with store.write() as transaction:
        insert_program(
            transaction,
            program_id="demo",
            concept_member=None,
            concept_path=None,
            registered_at=NOW,
            updated_at=NOW,
        )
        for member_id in (MEMBER_ID, OTHER_MEMBER_ID):
            insert_member(
                transaction,
                project_id=member_id,
                program_id="demo",
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=NOW,
                updated_at=NOW,
            )


def claimed_question(
    key: QuestionKey = KEY,
    *,
    member_id: str = MEMBER_ID,
    answering_run_id: str = ANSWERING_RUN,
) -> NewQuestion:
    return NewQuestion(
        key=key,
        member_id=member_id,
        question="What is the file length limit?",
        checkout="/work/a",
        slice_label="223 pause-handling",
        source_commit="abc123",
        passages=(PASSAGE,),
        answering_run_id=answering_run_id,
        waiting_reason=None,
        waiting_detail=None,
    )


def waiting_question(
    key: QuestionKey = KEY, *, member_id: str = MEMBER_ID
) -> NewQuestion:
    return NewQuestion(
        key=key,
        member_id=member_id,
        question="What is the file length limit?",
        checkout="/work/a",
        slice_label=None,
        source_commit=None,
        passages=None,
        answering_run_id=None,
        waiting_reason=DeclineReason.ANSWER_LIMIT_REACHED,
        waiting_detail="limit 3",
    )


HELD_REQUEST_ID = "request-a"


def insert_held_row(
    transaction: Transaction,
    key: QuestionKey = KEY,
    *,
    member_id: str = MEMBER_ID,
    request_id: str = HELD_REQUEST_ID,
    now: datetime = NOW,
) -> None:
    """A ``waiting_on_request`` row (slice 242), through its held insert."""
    held = HeldQuestion(key, member_id, "What did the request add?", "/work/a")
    assert insert_held(transaction, held, request_id, now)
