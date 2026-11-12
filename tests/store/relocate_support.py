"""A seeded legacy store for the relocate and state-move tests (slice 228, D2)."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from amoeba.answering.values import AnsweredBy
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from store.seed import (
    insert_answer,
    insert_member,
    insert_program,
    insert_question,
)

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
PROGRAM = "trial"
MEMBER = "cf-project-one"
RUN_IDS = ("run-a", "run-b", "run-c")
PAUSED_AT = "2026-11-01T11:00:00Z"
UPDATE_RESUME_LOG = "UPDATE answers SET resume_log = ? WHERE run_id = ?"


def seed_store(home: Path) -> Path:
    """Create ``home/amoeba.sqlite3`` with a program, a member, three questions and
    three answers whose ``resume_log`` is under ``home``, elsewhere, and null."""
    home.mkdir(parents=True, exist_ok=True)
    path = home / "amoeba.sqlite3"
    with Store.open(path) as store, store.write() as transaction:
        insert_program(
            transaction,
            program_id=PROGRAM,
            concept_member=None,
            concept_path=None,
            registered_at=NOW,
            updated_at=NOW,
        )
        insert_member(
            transaction,
            project_id=MEMBER,
            program_id=PROGRAM,
            rules_paths=("CLAUDE.md",),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=NOW,
            updated_at=NOW,
        )
        for run_id in RUN_IDS:
            insert_question(
                transaction,
                run_id=run_id,
                paused_at=PAUSED_AT,
                member_id=MEMBER,
                question=f"question of {run_id}?",
                checkout="/work/checkout",
                state=QuestionState.ANSWERED,
                answering_run_id=None,
                waiting_reason=None,
                claimed_at=NOW,
                updated_at=NOW,
            )
            insert_answer(
                transaction,
                run_id=run_id,
                paused_at=PAUSED_AT,
                answered_by=AnsweredBy.PM,
                answer="yes",
                recorded_at=NOW,
                resume_outcome=ResumeOutcome.RESUMED,
            )
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            UPDATE_RESUME_LOG,
            (str(home / "logs" / "resume" / "run-a" / "1.log"), "run-a"),
        )
        connection.execute(UPDATE_RESUME_LOG, ("/elsewhere/logs/run-b.log", "run-b"))
        connection.commit()
    return path
