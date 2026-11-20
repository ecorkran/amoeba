"""Shared by the standing-answer tests: a store with two programs and a recording cf.

``demo`` holds ``alpha`` and ``beta``; ``second`` holds ``gamma``. ``gone`` is known to
``cf`` but was removed from ``demo``; ``stranger`` is known to ``cf`` and in no
program. Seeded through the store's SQL, not ``set_up``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

from cf_fixtures import DEFAULT_WORKTREE
from store.seed import insert_member, insert_program

from amoeba.store.programs import remove_member
from amoeba.store.store import Store
from operations.set_up_support import FakeCf

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
#: The passage cap the operation tests give ``standing``.
MAX_CHARS = 1000
#: Program to its members' project ids.
LAYOUT = {"demo": ("alpha-id", "beta-id", "gone-id"), "second": ("gamma-id",)}
#: Context Forge's id and name for each project it knows.
PROJECTS = [
    ("alpha-id", "alpha"),
    ("beta-id", "beta"),
    ("gamma-id", "gamma"),
    ("gone-id", "gone"),
    ("stranger-id", "stranger"),
]


class RecordingCf(FakeCf):
    """``FakeCf`` that also keeps each call's keyword arguments (``cwd`` among them)."""

    def __init__(self) -> None:
        super().__init__(directory_fixture=DEFAULT_WORKTREE, projects=PROJECTS)
        self.keywords: list[dict[str, object]] = []

    def __call__(
        self, argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.keywords.append(kwargs)
        return super().__call__(argv, **kwargs)


def seeded_store(path: Path) -> Iterator[Store]:
    with Store.open(path) as store:
        with store.write() as transaction:
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
            remove_member(transaction, "gone-id", NOW)
        yield store


def standing_count(store: Store) -> int:
    with store.read() as transaction:
        row = transaction.execute("SELECT COUNT(*) FROM standing_answers").fetchone()
    return int(row[0])
