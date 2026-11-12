"""The schema holds no mirrored state (slice 224, D9).

Every ``(table, column)`` of a freshly migrated store is pinned below under the one
reason it exists. A new column fails this test until it is added here and to
``docs/store-contract.md``, which lists the same columns under the same reasons; that
is the moment to ask whether it mirrors something Context Forge or Squadron already
says. ``questions.checkout`` and ``questions.slice_label`` are record: where and
under which slice a pause happened, never read as current state.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from amoeba.store.store import Store

STORE_CONTRACT: Final = Path(__file__).parents[2] / "docs" / "store-contract.md"
INTERNAL_TABLE_PREFIX: Final = "sqlite_"

#: Reason to the ``table.column`` entries that exist for it.
COLUMN_REASONS: Final[dict[str, frozenset[str]]] = {
    # What happened: written once when it did, never updated to follow anything else.
    "record": frozenset(
        {
            "releases.seq",
            "releases.member_id",
            "releases.commit_sha",
            "releases.version",
            "releases.changed",
            "releases.touched",
            "releases.reported_at",
            "releases.versioned_at",
            "questions.run_id",
            "questions.paused_at",
            "questions.member_id",
            "questions.question",
            "questions.checkout",
            "questions.state",
            "questions.answering_run_id",
            "questions.waiting_reason",
            "questions.claimed_at",
            "questions.updated_at",
            "questions.slice_label",
            "questions.source_commit",
            "questions.passages",
            "questions.waiting_detail",
            "questions.evidence",
            "answers.seq",
            "answers.run_id",
            "answers.paused_at",
            "answers.answered_by",
            "answers.answer",
            "answers.recorded_at",
            "answers.resume_outcome",
            "answers.cited",
            "answers.resume_detail",
            "answers.resume_log",
            "answers.resume_at",
        }
    ),
    # Who is in a program: the PM's registration, the one thing only Amoeba knows.
    "membership": frozenset(
        {
            "programs.program_id",
            "programs.registered_at",
            "programs.updated_at",
            "members.project_id",
            "members.program_id",
            "members.registered_at",
            "members.updated_at",
            "dependency_pairs.program_id",
            "dependency_pairs.provider_id",
            "dependency_pairs.consumer_id",
            "dependency_pairs.registered_at",
            "dependency_pairs.updated_at",
        }
    ),
    # What the PM chose for a program or member, and the store's own bookkeeping.
    "settings": frozenset(
        {
            "programs.concept_member",
            "programs.concept_path",
            "members.rules_paths",
            "members.authorize_allow",
            "members.authorize_deny",
            "dependency_pairs.consumed",
            "schema_meta.id",
            "schema_meta.version",
        }
    ),
    # How far the PM has read the decisions.
    "marker": frozenset({"pm_marker.id", "pm_marker.last_seen_seq"}),
}


def _actual_columns(tmp_path: Path) -> set[str]:
    """Every ``table.column`` of a new store, from ``PRAGMA table_info``."""
    with Store.open(tmp_path / "amoeba.sqlite3") as store, store.read() as transaction:
        tables = [
            row[0]
            for row in transaction.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            if not row[0].startswith(INTERNAL_TABLE_PREFIX)
        ]
        return {
            f"{table}.{row[1]}"
            for table in tables
            for row in transaction.execute(f"PRAGMA table_info({table})")
        }


def test_every_column_is_pinned_under_one_reason(tmp_path: Path) -> None:
    pinned = [column for columns in COLUMN_REASONS.values() for column in columns]

    assert len(pinned) == len(set(pinned)), "a column is under two reasons"
    actual = _actual_columns(tmp_path)
    assert set(pinned) == actual, (
        f"unpinned: {sorted(actual - set(pinned))}; "
        f"pinned but absent: {sorted(set(pinned) - actual)}"
    )


def test_the_store_contract_lists_the_same_columns_under_the_same_reasons() -> None:
    text = STORE_CONTRACT.read_text(encoding="utf-8")

    documented = {reason: _documented(text, reason) for reason in COLUMN_REASONS}

    assert documented == COLUMN_REASONS


def _documented(text: str, reason: str) -> frozenset[str]:
    """The ``table.column`` entries of the contract's ``- **<reason>**:`` item."""
    match = re.search(
        rf"^- \*\*{reason}\*\*:(.*?)(?:\n\n|\n- \*\*|\Z)", text, re.S | re.M
    )
    assert match is not None, f"the store contract has no {reason!r} item"
    return frozenset(re.findall(r"`([a-z_]+\.[a-z_]+)`", match.group(1)))
