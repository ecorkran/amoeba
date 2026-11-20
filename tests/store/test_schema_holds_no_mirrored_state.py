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
            "answers.via",
            "answers.answer",
            "answers.recorded_at",
            "answers.resume_outcome",
            "answers.cited",
            "answers.resume_detail",
            "answers.resume_log",
            "answers.resume_at",
            "answers.retracted_at",
            "answers.retract_reason",
            "answers.resume_started_at",
            "questions.closed_reason",
            "questions.closed_detail",
            "questions.closed_at",
            "questions.request_id",
            "questions.start_attempted_at",
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
            "members.removed_at",
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
            "members.rules_from",
            "members.wake_command",
            "members.rules_paths",
            "members.authorize_allow",
            "members.authorize_deny",
            "dependency_pairs.consumed",
            "schema_meta.id",
            "schema_meta.version",
        }
    ),
    # What agents said to each other and where each request stands: Amoeba is the only
    # place this exists. A request's state is Amoeba's own, never read from Context
    # Forge or Squadron.
    "messages": frozenset(
        {
            "messages.message_id",
            "messages.kind",
            "messages.from_member",
            "messages.to_member",
            "messages.to_program",
            "messages.parent_id",
            "messages.depth",
            "messages.subject",
            "messages.body",
            "messages.state",
            "messages.result",
            "messages.result_commit",
            "messages.result_version",
            "messages.reason",
            "messages.accepted_at",
            "messages.created_at",
            "messages.state_changed_at",
            "messages.expires_at",
            "deliveries.seq",
            "deliveries.member_id",
            "deliveries.message_id",
            "deliveries.event",
            "deliveries.created_at",
            "message_rejections.id",
            "message_rejections.member_id",
            "message_rejections.operation",
            "message_rejections.to_ref",
            "message_rejections.message_id",
            "message_rejections.parent_id",
            "message_rejections.code",
            "message_rejections.detail",
            "message_rejections.created_at",
        }
    ),
    # What Amoeba started with nobody present, and how each start ended (244).
    "waking": frozenset(
        {
            "wakes.wake_id",
            "wakes.member_id",
            "wakes.directory",
            "wakes.command",
            "wakes.started_at",
            "wakes.deadline_at",
            "wakes.log_stem",
            "wakes.command_pid",
            "wakes.ended_at",
            "wakes.outcome",
            "wakes.exit_code",
            "wakes.detail",
        }
    ),
    # How far the PM has read the decisions.
    "marker": frozenset({"pm_marker.id", "pm_marker.last_seen_seq"}),
    # Rulings the PM gave ahead of time and whether each still holds (230 D1).
    "rulings": frozenset(
        {
            "standing_answers.id",
            "standing_answers.text",
            "standing_answers.reach",
            "standing_answers.program_id",
            "standing_answers.member_id",
            "standing_answers.given_at",
            "standing_answers.withdrawn_at",
            "standing_answers.withdraw_reason",
        }
    ),
    # Which amoeba-mcp processes are serving now, as their own heartbeats say.
    "presence": frozenset(
        {
            "sessions.session_id",
            "sessions.member_id",
            "sessions.client",
            "sessions.directory",
            "sessions.started_at",
            "sessions.heartbeat_at",
            "sessions.push_confirmed_at",
        }
    ),
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
