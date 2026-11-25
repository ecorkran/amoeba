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

from amoeba.operations.changes_models import ChangesResult
from amoeba.operations.decisions import DecisionsOutcome, DecisionsResult
from amoeba.operations.dismiss import DismissOutcome, DismissResult
from amoeba.operations.errors import MALFORMED_CALL, CallRefused
from amoeba.operations.here_document import (
    HereCaller,
    HereCheckout,
    HereNotAProject,
)
from amoeba.operations.list_registry import MembersView
from amoeba.operations.list_view import ListResult
from amoeba.operations.mark_read import MarkReadOutcome, MarkReadResult
from amoeba.operations.message_results import InboxResult
from amoeba.operations.retract import RetractOutcome, RetractResult
from amoeba.operations.runs_document import RunsDocument, runs_to_document
from amoeba.operations.served import (
    SERVED,
    ClientValues,
    Gather,
    HereKind,
    ServedEdges,
    ServedResult,
    client_values_from_body,
    gather_needed,
    result_document,
    result_from_document,
    run_served,
)
from amoeba.operations.standing_models import (
    StandingOutcome,
    StandingRejection,
    StandingResult,
    WithdrawOutcome,
    WithdrawResult,
)
from amoeba.operations.status import StatusOutcome, StatusResult
from amoeba.store.questions import insert_question
from amoeba.store.store import Store, Transaction
from amoeba.wire.protocol import SERVED_OPERATIONS
from amoeba.wire.times import DOOR_VERSION

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
        door_version=DOOR_VERSION,
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


def test_the_operations_that_read_the_config_are_these() -> None:
    """``inbox`` and ``changes`` read none; the rest of the nine and ``standing`` do,
    so a hub without ``config.yaml`` refuses them as ``hub_error`` (260 D6)."""
    assert {name for name, entry in SERVED.items() if entry.needs_config} == {
        "standing",
        "add",
        "rm",
        "list",
        "status",
        "send",
        "reply",
        "cancel",
        "report_release",
        "answer",
    }


def test_an_unserved_name_raises_value_error(store: Store) -> None:
    with pytest.raises(ValueError, match="handle_pause"):
        run_served("handle_pause", store, {}, _edges(store))


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


# --- the gathered values (slice 261, D5) -------------------------------------------

CALLER_DOCUMENT = {"project_id": "cf-caller"}
CHECKOUT_DOCUMENT = {
    "project_id": "cf-new",
    "name": "new-repo",
    "path": "/work/new",
    "origin": "github.com/org/new-repo",
}


@pytest.mark.parametrize(
    ("name", "document", "here", "runs"),
    [
        ("status", {}, HereKind.CALLER, True),
        ("list", {}, HereKind.CALLER, True),
        ("list", {"subject": "members"}, None, False),
        ("list", {"subject": "programs"}, None, False),
        ("list", {"subject": "dependencies"}, None, False),
        ("list", {"subject": "standing"}, None, False),
        ("inbox", {}, HereKind.CALLER, False),
        ("changes", {}, HereKind.CALLER, False),
        ("send", {}, HereKind.CALLER, False),
        ("reply", {}, HereKind.CALLER, False),
        ("cancel", {}, HereKind.CALLER, False),
        ("report_release", {}, HereKind.CALLER, False),
        ("add", {}, HereKind.CHECKOUT, False),
        ("add", {"project": "forge"}, None, False),
        ("add", {"name": "forge"}, HereKind.CHECKOUT, False),
        ("rm", {}, HereKind.CALLER, False),
        ("rm", {"members": ["forge"]}, None, False),
        ("rm", {"checkout": "/work/forge"}, None, False),
        ("decisions", {}, None, False),
        ("standing", {}, None, False),
    ],
)
def test_what_each_call_needs_gathered(
    name: str, document: object, here: HereKind | None, runs: bool
) -> None:
    needed = gather_needed(name, document)
    assert (needed.here, needed.runs) == (here, runs)


def test_send_also_needs_the_logs_directory_and_answer_its_door() -> None:
    """262 D7, D8: the client sends them beside the document."""
    assert gather_needed("send", {}) == Gather(here=HereKind.CALLER, logs_dir=True)
    assert gather_needed("answer", {}) == Gather(via=True)


def test_a_document_that_does_not_parse_needs_nothing_gathered() -> None:
    """The operation rejects it as malformed; no ``cf`` call is made for it."""
    for name in ("add", "rm", "list"):
        assert gather_needed(name, {"unknown_field": 1}) == Gather()


def test_values_are_parsed_from_the_body_for_what_the_call_needs() -> None:
    body: dict[str, object] = {
        "here": CALLER_DOCUMENT,
        "runs": runs_to_document(RunsDocument()),
    }

    values = client_values_from_body("status", {}, body)

    assert values.here == HereCaller(project_id="cf-caller")
    assert values.runs == RunsDocument()


def test_add_parses_the_checkout_shape_and_the_not_a_project_shape() -> None:
    checkout = client_values_from_body("add", {}, {"here": CHECKOUT_DOCUMENT})
    nowhere = client_values_from_body("add", {}, {"here": {"not_a_project": "no"}})

    assert isinstance(checkout.here, HereCheckout)
    assert checkout.here.origin == "github.com/org/new-repo"
    assert isinstance(nowhere.here, HereNotAProject)


def test_a_key_the_call_does_not_need_is_ignored_even_when_it_is_garbage() -> None:
    values = client_values_from_body(
        "list", {"subject": "members"}, {"here": 5, "runs": "junk"}
    )

    assert values == ClientValues()


@pytest.mark.parametrize(
    ("name", "body", "field"),
    [
        ("status", {"runs": {}}, "here"),
        ("status", {"here": CALLER_DOCUMENT}, "runs"),
        ("status", {"here": CALLER_DOCUMENT, "runs": []}, "runs"),
        ("status", {"here": [], "runs": {}}, "here"),
        ("inbox", {"here": {"wrong": 1}}, "here"),
        ("add", {"here": CALLER_DOCUMENT}, "here"),
        (
            "add",
            {"here": {**CHECKOUT_DOCUMENT, "origin": "git@host:org/x.git"}},
            "here",
        ),
    ],
)
def test_a_missing_or_bad_value_is_a_malformed_call_naming_the_key(
    name: str, body: dict[str, object], field: str
) -> None:
    with pytest.raises(CallRefused) as raised:
        client_values_from_body(name, {}, body)

    assert raised.value.code == MALFORMED_CALL
    assert field in raised.value.message
    assert "git@host" not in raised.value.message


def test_status_and_list_run_on_a_seeded_store_with_hand_built_values(
    store: Store,
) -> None:
    edges = _edges(store)
    values = ClientValues(here=HereNotAProject(not_a_project="x"), runs=RunsDocument())

    status = run_served("status", store, {}, edges, values)
    listed = run_served("list", store, {}, edges, values)
    members = run_served("list", store, {"subject": "members"}, edges, ClientValues())

    assert _is(status, StatusResult).outcome is StatusOutcome.LISTED
    assert _is(listed, ListResult).status.outcome is StatusOutcome.LISTED
    assert len(_is(members, MembersView).members) == 2


def test_inbox_and_changes_run_with_the_caller(store: Store) -> None:
    edges = _edges(store)
    values = ClientValues(here=HereCaller(project_id=CORE))

    inbox = run_served("inbox", store, {}, edges, values)
    changes = run_served(
        "changes", store, {"since": "2026-01-01T00:00:00+00:00"}, edges, values
    )

    assert _is(inbox, InboxResult).outcome.value == "listed"
    assert _is(changes, ChangesResult).outcome.value == "listed"


def test_a_list_result_is_rebuilt_from_its_document_by_the_request_subject(
    store: Store,
) -> None:
    edges = _edges(store)
    values = ClientValues(here=HereNotAProject(not_a_project="x"), runs=RunsDocument())
    for request in ({}, {"all": True}, {"subject": "members"}, {"subject": "programs"}):
        shown = run_served(
            "list",
            store,
            request,
            edges,
            values if not request.get("subject") else ClientValues(),
        )

        rebuilt = result_from_document("list", result_document(shown), request)

        assert rebuilt == shown
