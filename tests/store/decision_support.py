"""Two programs, two members and answers on them, for the decision tests (slice 224)."""

from __future__ import annotations

from datetime import datetime, timedelta

from amoeba.answering.values import AnsweringEvidence
from amoeba.store.answers import Settled, add_pm_answer, settle_answered
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from store.question_support import (
    ANSWERING_RUN,
    NOW,
    claimed_question,
    waiting_question,
)
from store.seed import insert_member, insert_program

TRADING = "trading"
TOOLS = "tools"
CORE = "member-core"
LINT = "member-lint"
FIRST = QuestionKey("run-1", "2026-11-10T09:00:00+00:00")
SECOND = QuestionKey("run-2", "2026-11-10T10:00:00+00:00")
THIRD = QuestionKey("run-3", "2026-11-10T11:00:00+00:00")


def at(minutes: int) -> datetime:
    return NOW + timedelta(minutes=minutes)


def seed_programs(opened: Store) -> None:
    """Program ``trading`` with member ``CORE``, program ``tools`` with ``LINT``."""
    with opened.write() as transaction:
        for program, member in ((TRADING, CORE), (TOOLS, LINT)):
            insert_program(
                transaction,
                program_id=program,
                concept_member=None,
                concept_path=None,
                registered_at=NOW,
                updated_at=NOW,
            )
            insert_member(
                transaction,
                project_id=member,
                program_id=program,
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=NOW,
                updated_at=NOW,
            )


def automatic_answer(store: Store, key: QuestionKey, member: str, minutes: int) -> int:
    with store.write() as transaction:
        insert_question(
            transaction,
            claimed_question(key, member_id=member),
            now=at(minutes),
        )
    settled = settle_answered(
        store,
        key,
        ANSWERING_RUN,
        answer=f"auto {key.run_id}",
        cited=("r1",),
        evidence=AnsweringEvidence(verdict="yes", reason="cited"),
        gate=lambda _prior: None,
        now=at(minutes),
    )
    assert isinstance(settled, Settled)
    return settled.answer_seq


def waiting_then_pm(store: Store, key: QuestionKey, member: str, minutes: int) -> int:
    with store.write() as transaction:
        insert_question(
            transaction, waiting_question(key, member_id=member), now=at(minutes)
        )
        return add_pm_answer(transaction, key, f"pm {key.run_id}", now=at(minutes))
