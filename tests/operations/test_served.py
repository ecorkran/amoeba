"""``run_served``: the six served operations, one function (slice 260, D8, D11)."""

from __future__ import annotations

import sqlite3
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fault_injection import InjectedFailureError
from store.decision_support import (
    CORE,
    FIRST,
    LINT,
    SECOND,
    THIRD,
    TRADING,
    at,
    automatic_answer,
    seed_programs,
    waiting_then_pm,
)
from store.question_support import NOW, claimed_question
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.decisions import DecisionsOutcome, DecisionsResult
from amoeba.operations.dismiss import DismissOutcome, DismissResult
from amoeba.operations.mark_read import MarkReadOutcome, MarkReadResult
from amoeba.operations.retract import RetractOutcome, RetractResult
from amoeba.operations.served import (
    SERVED,
    ServedEdges,
    ServedResult,
    run_served,
)
from amoeba.operations.standing_models import (
    StandingOutcome,
    StandingRejection,
    StandingResult,
    WithdrawOutcome,
    WithdrawResult,
)
from amoeba.store.questions import insert_question
from amoeba.store.store import Store, Transaction
from amoeba.wire.protocol import SERVED_OPERATIONS

STAMP = NOW.isoformat()


def _is[ResultT: ServedResult](result: ServedResult, kind: type[ResultT]) -> ResultT:
    assert isinstance(result, kind)
    return result


def _edges(store: Store, *, max_chars: int | None = None) -> ServedEdges:
    config = user_config()
    if max_chars is not None:
        config = config.model_copy(update={"passages_max_chars": max_chars})
    return ServedEdges(
        clock=lambda: NOW,
        load_config=lambda: config,
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


def test_the_registry_is_exactly_the_served_operations() -> None:
    registered, listed = set(SERVED), set(SERVED_OPERATIONS)
    assert registered == listed, (
        f"in SERVED but not in wire.protocol.SERVED_OPERATIONS: {registered - listed}; "
        f"in SERVED_OPERATIONS but with no SERVED entry: {listed - registered}"
    )


def test_only_standing_reads_the_config() -> None:
    assert {name for name, entry in SERVED.items() if entry.needs_config} == {
        "standing"
    }


def test_an_unserved_name_raises_value_error(store: Store) -> None:
    with pytest.raises(ValueError, match="add"):
        run_served("add", store, {}, _edges(store))


def test_each_of_the_six_runs_on_a_seeded_store(store: Store) -> None:
    edges = _edges(store)
    first = automatic_answer(store, FIRST, CORE, 1)
    pm_answer = waiting_then_pm(store, SECOND, LINT, 2)
    with store.write() as transaction:
        insert_question(transaction, claimed_question(THIRD, member_id=CORE), now=at(3))

    listed = _is(run_served("decisions", store, {}, edges), DecisionsResult)
    marked = _is(
        run_served("mark_read", store, {"through": first}, edges), MarkReadResult
    )
    given = _is(
        run_served("standing", store, {"text": "a rule"}, edges), StandingResult
    )
    withdrawn = _is(
        run_served(
            "withdraw",
            store,
            {"standing_id": given.standing_id, "reason": "done"},
            edges,
        ),
        WithdrawResult,
    )
    dismissed = _is(
        run_served(
            "dismiss",
            store,
            {"run_id": THIRD.run_id, "paused_at": THIRD.paused_at, "reason": "no"},
            edges,
        ),
        DismissResult,
    )
    retracted = _is(
        run_served(
            "retract", store, {"answer_seq": pm_answer, "reason": "wrong"}, edges
        ),
        RetractResult,
    )

    assert listed.outcome is DecisionsOutcome.LISTED
    assert marked.outcome is MarkReadOutcome.MOVED
    assert given.outcome is StandingOutcome.GIVEN
    assert withdrawn.outcome is WithdrawOutcome.WITHDRAWN
    assert dismissed.outcome is DismissOutcome.DISMISSED
    assert retracted.outcome is RetractOutcome.RETRACTED


def test_names_and_references_are_store_reads_and_start_no_process(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_subprocess(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a served operation started a process (cf or sq)")

    monkeypatch.setattr(subprocess, "run", no_subprocess)
    monkeypatch.setattr(subprocess, "Popen", no_subprocess)
    edges = _edges(store)
    automatic_answer(store, FIRST, CORE, 1)

    listed = _is(run_served("decisions", store, {}, edges), DecisionsResult)
    by_id = _is(
        run_served("standing", store, {"text": "r1", "member": CORE}, edges),
        StandingResult,
    )
    by_name = _is(
        run_served("standing", store, {"text": "r2", "member": "core-name"}, edges),
        StandingResult,
    )
    unknown = _is(
        run_served("standing", store, {"text": "r3", "member": "nobody"}, edges),
        StandingResult,
    )

    assert [(r.member.id, r.member.name) for r in listed.records] == [
        (CORE, "core-name")
    ]
    assert by_id.outcome is StandingOutcome.GIVEN
    assert by_id.member == CORE
    assert by_name.outcome is StandingOutcome.GIVEN
    assert by_name.member == CORE
    assert unknown.rejection is StandingRejection.NO_SUCH_MEMBER


def test_a_standing_answer_for_a_program_reaches_it(store: Store) -> None:
    edges = _edges(store)

    result = run_served("standing", store, {"text": "r", "program": TRADING}, edges)

    assert _is(result, StandingResult).outcome is StandingOutcome.GIVEN


# --- the call scope with the five writing operations ---------------------------


def _all_rows(store: Store, skip: str) -> dict[str, list[tuple[object, ...]]]:
    with store.read() as transaction:
        tables = [
            row[0]
            for row in transaction.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            table: [tuple(row) for row in transaction.execute(f"SELECT * FROM {table}")]
            for table in tables
            if table != skip
        }


def _seed_for(store: Store, name: str) -> dict[str, object]:
    """Seed what ``name`` needs and return its document."""
    first = automatic_answer(store, FIRST, CORE, 1)
    if name == "mark_read":
        return {"through": first}
    if name == "retract":
        pm = waiting_then_pm(store, SECOND, LINT, 2)
        return {"answer_seq": pm, "reason": "wrong"}
    if name == "dismiss":
        with store.write() as transaction:
            insert_question(
                transaction, claimed_question(THIRD, member_id=CORE), now=at(3)
            )
        return {"run_id": THIRD.run_id, "paused_at": THIRD.paused_at, "reason": "no"}
    if name == "standing":
        return {"text": "a ruling"}
    given = run_served("standing", store, {"text": "to withdraw"}, _edges(store))
    return {"standing_id": _is(given, StandingResult).standing_id, "reason": "done"}


def _last_write_statement(store: Store, name: str, document: object) -> str:
    """The text of the last INSERT, UPDATE or DELETE ``name`` runs on ``document``."""
    seen: list[str] = []
    real = Transaction.execute

    def spy(
        self: Transaction, statement: str, parameters: tuple[object, ...] = ()
    ) -> sqlite3.Cursor:
        seen.append(statement)
        return real(self, statement, parameters)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Transaction, "execute", spy)
        run_served(name, store, document, _edges(store))
    writes = [
        s
        for s in seen
        if s.lstrip().split(None, 1)[0] in {"INSERT", "UPDATE", "DELETE"}
    ]
    assert writes, f"{name} wrote nothing"
    return writes[-1]


@pytest.mark.parametrize(
    "name", sorted(["mark_read", "dismiss", "retract", "standing", "withdraw"])
)
def test_a_writing_operation_that_fails_inside_a_call_scope_leaves_only_the_outer_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    with open_local_store(tmp_path / "probe.sqlite3") as probe:
        seed_programs(probe)
        statement = _last_write_statement(probe, name, _seed_for(probe, name))

    with open_local_store(tmp_path / "amoeba.sqlite3") as store:
        seed_programs(store)
        document = _seed_for(store, name)
        before = _all_rows(store, skip="programs")
        real = Transaction.execute

        def failing(
            self: Transaction, text: str, parameters: tuple[object, ...] = ()
        ) -> sqlite3.Cursor:
            if text == statement:
                raise InjectedFailureError(text.strip())
            return real(self, text, parameters)

        with store.call_scope():
            with store.write() as outer:
                outer.execute(
                    "INSERT INTO programs (program_id, registered_at, updated_at, "
                    "owner_id) VALUES ('outer', ?, ?, ?)",
                    (STAMP, STAMP, outer.acting("programs").owner_id),
                )
            monkeypatch.setattr(Transaction, "execute", failing)
            try:
                with store.write():
                    run_served(name, store, document, _edges(store))
            except InjectedFailureError:
                pass  # as handle_call will: roll the operation back, keep the scope
            monkeypatch.setattr(Transaction, "execute", real)

        after = _all_rows(store, skip="programs")
        with store.read() as transaction:
            programs = [
                r[0] for r in transaction.execute("SELECT program_id FROM programs")
            ]

    assert after == before
    assert "outer" in programs


def test_standings_overflow_path_stores_nothing_and_keeps_the_outer_write(
    store: Store,
) -> None:
    edges = _edges(store, max_chars=5)
    before = _all_rows(store, skip="programs")

    with store.call_scope():
        with store.write() as outer:
            outer.execute(
                "INSERT INTO programs (program_id, registered_at, updated_at, "
                "owner_id) VALUES ('outer', ?, ?, ?)",
                (STAMP, STAMP, outer.acting("programs").owner_id),
            )
        with store.write():
            result: ServedResult = run_served(
                "standing", store, {"text": "far longer than five"}, edges
            )

    assert _is(result, StandingResult).rejection is StandingRejection.TOO_LONG
    assert _all_rows(store, skip="programs") == before
    with store.read() as transaction:
        assert (
            transaction.execute(
                "SELECT COUNT(*) FROM programs WHERE program_id = 'outer'"
            ).fetchone()[0]
            == 1
        )
