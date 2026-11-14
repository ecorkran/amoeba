"""Seed the program and members the ``releases`` foreign key needs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from amoeba.store.store import Store
from store.seed import insert_member, insert_program

PROGRAM = "demo"
PROVIDER = "provider-id"
OTHER_PROVIDER = "other-provider-id"
START = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
FULL_HASH = "a" * 40
OTHER_HASH = "b" * 40
THIRD_HASH = "c" * 40


def at(hours: int) -> datetime:
    """A test time ``hours`` after ``START``."""
    return START + timedelta(hours=hours)


def seed_members(store: Store) -> None:
    """One program with the two members whose reports the tests write."""
    with store.write() as transaction:
        insert_program(
            transaction,
            program_id=PROGRAM,
            concept_member=None,
            concept_path=None,
            registered_at=START,
            updated_at=START,
        )
        for member in (PROVIDER, OTHER_PROVIDER):
            insert_member(
                transaction,
                project_id=member,
                program_id=PROGRAM,
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=START,
                updated_at=START,
            )
