"""The acting machine: who every inserted record belongs to (slice 260, D12)."""

from __future__ import annotations

import importlib
import pkgutil
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

import amoeba.store
from amoeba.config.home import state_layout
from amoeba.operations.state_move import open_state_store
from amoeba.store.answers import add_pm_answer
from amoeba.store.deliveries import write_delivery
from amoeba.store.errors import NoActingMachineError, StoreError
from amoeba.store.machines import LOCAL_MACHINE_NAME, the_owner
from amoeba.store.message_rejections import record_rejection
from amoeba.store.messages import insert_request
from amoeba.store.models import MemberSettings, QuestionKey, Session
from amoeba.store.programs import upsert_member, upsert_pair, upsert_program
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.store.releases import insert_release
from amoeba.store.sessions import upsert_session
from amoeba.store.standing import give_standing
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import (
    ConsumedMode,
    DeliveryEvent,
    QuestionState,
    RulesFrom,
    StandingReach,
)
from amoeba.store.wakes import WakeLimits, claim_wake
from store.seed import insert_checkout, insert_member, insert_program, mark_wake_wanted
from store.seed import insert_question as seed_question

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
RECORD_TABLES = (
    "programs", "members", "dependency_pairs", "releases", "questions", "answers",
    "standing_answers", "messages", "deliveries", "message_rejections", "sessions",
    "wakes",
)  # fmt: skip
SEEDED_KEY = QuestionKey("run-seed", "2026-11-20T11:00:00Z")
LIMITS = WakeLimits(timeout_seconds=600, max_per_day=3, session_stale_seconds=90)


def _seed(path: Path) -> None:
    """The rows each insert below refers to, written as the local machine."""
    with open_local_store(path) as store, store.write() as transaction:
        insert_program(
            transaction,
            program_id="demo",
            concept_member=None,
            concept_path=None,
            registered_at=NOW,
            updated_at=NOW,
        )
        for member, command in (("m1", None), ("m2", "wake-it")):
            insert_member(
                transaction,
                project_id=member,
                program_id="demo",
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=NOW,
                updated_at=NOW,
            )
            insert_checkout(
                transaction,
                member_id=member,
                cf_project_id=member,
                path=f"/work/{member}",
                wake_command=command,
                now=NOW,
            )
        seed_question(
            transaction,
            run_id=SEEDED_KEY.run_id,
            paused_at=SEEDED_KEY.paused_at,
            member_id="m1",
            question="q",
            checkout="/c",
            state=QuestionState.WAITING_ON_PM,
            answering_run_id=None,
            waiting_reason="no_passage",
            claimed_at=NOW,
            updated_at=NOW,
        )
        mark_wake_wanted(transaction, "m2", NOW)
        insert_request(
            transaction,
            message_id="r1",
            from_member="m1",
            to_member="m2",
            parent_id=None,
            parent_depth=None,
            subject="s",
            body="b",
            ttl=timedelta(days=1),
            now=NOW,
        )


def _inserts() -> dict[str, Callable[[Transaction], object]]:
    """One store-function insert per record table, none of which exists yet."""
    new_question = NewQuestion(
        key=QuestionKey("run-new", "2026-11-20T11:30:00Z"),
        member_id="m1",
        question="q",
        checkout="/c",
        slice_label=None,
        source_commit=None,
        passages=None,
        answering_run_id="answering-1",
        waiting_reason=None,
        waiting_detail=None,
    )
    settings = MemberSettings(
        project_id="m3",
        rules_paths=(),
        authorize_allow=(),
        authorize_deny=(),
        rules_from=RulesFrom.NAMED,
    )
    session = Session("s1", "m1", "claude", "/c", NOW, NOW, None)
    return {
        "programs": lambda tx: upsert_program(
            tx, program_id="other", concept_member=None, concept_path=None, now=NOW
        ),
        "members": lambda tx: upsert_member(
            tx, program_id="demo", settings=settings, name="m3", now=NOW
        ),
        "dependency_pairs": lambda tx: upsert_pair(
            tx,
            program_id="demo",
            provider_id="m2",
            consumer_id="m1",
            consumed=ConsumedMode.FROM_SOURCE,
            now=NOW,
        ),
        "releases": lambda tx: insert_release(tx, "m1", "abc", None, "x", (), NOW),
        "questions": lambda tx: insert_question(tx, new_question, now=NOW),
        "answers": lambda tx: add_pm_answer(tx, SEEDED_KEY, "a", now=NOW, via=None),
        "standing_answers": lambda tx: give_standing(
            tx, "rule", StandingReach.ALL, None, None, NOW
        ),
        "messages": lambda tx: insert_request(
            tx,
            message_id="r2",
            from_member="m1",
            to_member="m2",
            parent_id=None,
            parent_depth=None,
            subject="s",
            body="b",
            ttl=timedelta(days=1),
            now=NOW,
        ),
        "deliveries": lambda tx: write_delivery(
            tx, "m2", "r1", DeliveryEvent.SENT, NOW
        ),
        "message_rejections": lambda tx: record_rejection(
            tx, "m1", "send", None, None, None, "c", "d", NOW
        ),
        "sessions": lambda tx: upsert_session(tx, session),
        "wakes": lambda tx: claim_wake(tx, "m2", NOW, LIMITS, "w1", "/log"),
    }


def _count(store: Store, table: str) -> int:
    with store.read() as transaction:
        row = transaction.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])


def test_the_inserts_cover_every_record_table() -> None:
    assert tuple(_inserts()) == RECORD_TABLES


@pytest.mark.parametrize("table", RECORD_TABLES)
def test_an_insert_with_no_acting_machine_fails_and_writes_nothing(
    tmp_path: Path, table: str
) -> None:
    path = tmp_path / "amoeba.sqlite3"
    _seed(path)
    insert = _inserts()[table]

    with Store.open(path) as store:
        before = _count(store, table)
        with pytest.raises(NoActingMachineError, match=table), store.write() as tx:
            insert(tx)

        assert _count(store, table) == before


@pytest.mark.parametrize("table", RECORD_TABLES)
def test_an_insert_acting_as_local_succeeds(tmp_path: Path, table: str) -> None:
    path = tmp_path / "amoeba.sqlite3"
    _seed(path)

    with open_local_store(path) as store:
        before = _count(store, table)
        with store.write() as tx:
            _inserts()[table](tx)

        assert _count(store, table) == before + 1


def test_open_state_store_makes_local_once_with_the_owner_and_no_token() -> None:
    layout = state_layout()
    open_state_store(layout).close()
    open_state_store(layout).close()

    with Store.open(layout.store_path) as store, store.read() as transaction:
        machines = transaction.execute(
            "SELECT name, owner_id, token_hash FROM machines"
        ).fetchall()
        owner = the_owner(transaction)

    assert [tuple(row) for row in machines] == [(LOCAL_MACHINE_NAME, owner, None)]


def test_records_written_through_the_local_opener_carry_the_owner_and_machine() -> None:
    store = open_state_store(state_layout())
    with store.write() as tx:
        upsert_program(
            tx, program_id="demo", concept_member=None, concept_path=None, now=NOW
        )
        upsert_member(
            tx,
            program_id="demo",
            settings=MemberSettings("m1", (), (), (), RulesFrom.NAMED),
            name="m1",
            now=NOW,
        )
        upsert_session(tx, Session("s1", "m1", "claude", "/c", NOW, NOW, None))
    with store.read() as tx:
        owner = the_owner(tx)
        local = tx.execute(
            "SELECT machine_id FROM machines WHERE name = ?", (LOCAL_MACHINE_NAME,)
        ).fetchone()[0]
        program_owner = tx.execute("SELECT owner_id FROM programs").fetchone()[0]
        session = tx.execute("SELECT owner_id, machine_id FROM sessions").fetchone()
    store.close()

    assert program_owner == owner
    assert tuple(session) == (owner, local)


def test_the_owner_fails_with_no_row_and_with_two(tmp_path: Path) -> None:
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        with store.write() as tx:
            assert the_owner(tx) > 0
            tx.execute("DELETE FROM owners")
        with pytest.raises(StoreError, match="exactly one owner"), store.read() as tx:
            the_owner(tx)
        with store.write() as tx:
            tx.execute("INSERT INTO owners (name, created_at) VALUES ('a', 't')")
            tx.execute("INSERT INTO owners (name, created_at) VALUES ('b', 't')")
        with pytest.raises(StoreError, match="exactly one owner"), store.read() as tx:
            the_owner(tx)


INSERT_TABLE = re.compile(r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(\w+)", re.IGNORECASE)


def _sql_constants() -> list[str]:
    """Every string constant of the store's ``sql*`` modules."""
    found: list[str] = []
    for module_info in pkgutil.iter_modules(amoeba.store.__path__):
        if not module_info.name.startswith("sql"):
            continue
        module = importlib.import_module(f"amoeba.store.{module_info.name}")
        found.extend(
            value
            for name, value in vars(module).items()
            if name.isupper() and isinstance(value, str)
        )
    return found


def test_every_record_insert_statement_names_the_owner() -> None:
    per_table: dict[str, list[str]] = {table: [] for table in RECORD_TABLES}
    for statement in _sql_constants():
        match = INSERT_TABLE.search(statement)
        if match and match.group(1) in per_table:
            per_table[match.group(1)].append(statement)

    assert all(per_table.values()), [t for t, found in per_table.items() if not found]
    unbound = [s for found in per_table.values() for s in found if "owner_id" not in s]
    assert not unbound
    sessions = per_table["sessions"]
    assert all("machine_id" in statement for statement in sessions)
