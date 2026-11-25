"""Question and wake inserts bind the acting machine, and the by-machine reads find
them (slice 262, D14)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from store_open import open_local_store

from amoeba.store import sql_held, sql_local_work, sql_wakes
from amoeba.store.held_questions import HeldQuestion, insert_held
from amoeba.store.machines import LOCAL_MACHINE_NAME
from amoeba.store.models import QuestionKey
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from amoeba.store.wakes import WakeLimits, claim_wake
from amoeba.wire.times import DOOR_VERSION
from store.seed import insert_checkout, insert_member, insert_program, mark_wake_wanted

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
LIMITS = WakeLimits(
    timeout_seconds=600,
    max_per_day=3,
    session_stale_seconds=90,
    door_version=DOOR_VERSION,
)
CLAIMED = QuestionKey("run-claimed", "2026-11-20T11:00:00Z")
HELD = QuestionKey("run-held", "2026-11-20T11:05:00Z")


def _seed_member(transaction: Transaction) -> None:
    insert_program(
        transaction,
        program_id="demo",
        concept_member=None,
        concept_path=None,
        registered_at=NOW,
        updated_at=NOW,
    )
    insert_member(
        transaction,
        project_id="m1",
        program_id="demo",
        rules_paths=(),
        authorize_allow=(),
        authorize_deny=(),
        registered_at=NOW,
        updated_at=NOW,
    )
    insert_checkout(
        transaction,
        member_id="m1",
        cf_project_id="m1",
        path="/work/m1",
        wake_command="wake-it",
        now=NOW,
    )


def _write_each_kind(transaction: Transaction) -> None:
    _seed_member(transaction)
    assert insert_question(
        transaction,
        NewQuestion(
            key=CLAIMED,
            member_id="m1",
            question="q",
            checkout="/work/m1",
            slice_label=None,
            source_commit=None,
            passages=None,
            answering_run_id="answering-1",
            waiting_reason=None,
            waiting_detail=None,
        ),
        now=NOW,
    )
    assert insert_held(
        transaction, HeldQuestion(HELD, "m1", "q", "/work/m1"), "request-1", NOW
    )
    mark_wake_wanted(transaction, "m1", NOW)
    assert claim_wake(transaction, "m1", NOW, LIMITS, "w1", "/log") is not None


def test_inserts_through_the_store_functions_carry_the_acting_machine(
    tmp_path: Path,
) -> None:
    with open_local_store(tmp_path / "amoeba.sqlite3") as store:
        with store.write() as transaction:
            _write_each_kind(transaction)

        with store.read() as transaction:
            local = transaction.execute(
                "SELECT machine_id FROM machines WHERE name = ?", (LOCAL_MACHINE_NAME,)
            ).fetchone()[0]
            question_machines = transaction.execute(
                "SELECT machine_id FROM questions"
            ).fetchall()
            wake_machines = transaction.execute(
                "SELECT machine_id FROM wakes"
            ).fetchall()

    assert question_machines == [(local,), (local,)]
    assert wake_machines == [(local,)]


def _find(store: Store) -> tuple[int, ...]:
    with store.read() as transaction:
        return tuple(
            int(row[0])
            for row in transaction.execute("SELECT machine_id FROM machines")
        )


def test_the_by_machine_reads_find_only_that_machines_rows(tmp_path: Path) -> None:
    with open_local_store(tmp_path / "amoeba.sqlite3") as store:
        with store.write() as transaction:
            _write_each_kind(transaction)
            transaction.execute(
                "INSERT INTO machines (name, owner_id, created_at) "
                "VALUES ('other', (SELECT owner_id FROM owners), 't')"
            )
        (local, other) = _find(store)

        with store.read() as transaction:
            open_local = transaction.execute(
                sql_local_work.SELECT_OPEN_QUESTIONS_OF_MACHINE,
                (local, *_open_parameters()),
            ).fetchall()
            open_other = transaction.execute(
                sql_local_work.SELECT_OPEN_QUESTIONS_OF_MACHINE,
                (other, *_open_parameters()),
            ).fetchall()
            held = transaction.execute(
                sql_held.SELECT_HELD_ROWS_OF_MACHINE,
                (QuestionState.WAITING_ON_REQUEST.value, local),
            ).fetchall()
            wakes = transaction.execute(
                sql_wakes.SELECT_WAKES_OF_MACHINE, (local,)
            ).fetchall()
            name = transaction.execute(
                sql_local_work.SELECT_QUESTION_MACHINE_NAME,
                (CLAIMED.run_id, CLAIMED.paused_at),
            ).fetchone()
            wakes_elsewhere = transaction.execute(
                sql_wakes.SELECT_WAKES_OF_MACHINE, (other,)
            ).fetchall()

    assert [row[0] for row in open_local] == [CLAIMED.run_id, HELD.run_id]
    assert open_other == []
    assert [row[0] for row in held] == [HELD.run_id]
    assert [row[0] for row in wakes] == ["w1"]
    assert wakes_elsewhere == []
    assert name == (LOCAL_MACHINE_NAME,)


def _open_parameters() -> tuple[str, ...]:
    """The open clause's five: claimed, waiting_on_pm, waiting_on_request, answered,
    refused."""
    return (
        QuestionState.CLAIMED.value,
        QuestionState.WAITING_ON_PM.value,
        QuestionState.WAITING_ON_REQUEST.value,
        QuestionState.ANSWERED.value,
        ResumeOutcome.REFUSED.value,
    )
