"""The runs each machine reports through ``status`` and what the others show of them
(slice 263, 7.1, D11), through the hub door with two machines."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from hub.call_support import ALPHA_TOKEN, BETA_TOKEN, HubRig, build_rig, result_of
from store.decision_support import CORE
from store.question_support import NOW
from store.seed import insert_question

from amoeba.operations.here_document import HereCaller
from amoeba.operations.runs_document import (
    LookupKind,
    OpenRun,
    RunCheckpoint,
    RunLookup,
    RunsDocument,
    runs_to_document,
)
from amoeba.store.machine_runs import get_machine_runs
from amoeba.store.machines import machine_id_by_name
from amoeba.store.models import Session
from amoeba.store.sessions import upsert_session
from amoeba.store.vocabulary import QuestionState
from amoeba.wire.protocol import DoneReply, RefusalCode, RefusedReply
from amoeba.wire.times import DOOR_VERSION

CALLER = HereCaller(project_id=CORE).model_dump()
PAUSED_AT = "2026-11-21T10:00:00Z"


def _paused_run(run_id: str = "run-a1") -> OpenRun:
    return OpenRun(
        run_id=run_id,
        pipeline="p6-implement",
        status="paused",
        working_directory="/work/alpha-core",
        checkpoint=RunCheckpoint(kind="gate", paused_at=PAUSED_AT, question="Ship?"),
        lookup=RunLookup(kind=LookupKind.PROJECT, project_id=CORE),
    )


def _status(
    rig: HubRig,
    token: str,
    runs: RunsDocument | dict[str, object],
    *,
    call_id: str = "call-1",
    name: str = "status",
) -> DoneReply:
    document = runs if isinstance(runs, dict) else runs_to_document(runs)
    reply = rig.call(
        name,
        {},
        token=token,
        call_id=call_id,
        extra={"here": CALLER, "runs": document},
    )
    parsed = result_of(reply)
    assert isinstance(parsed, DoneReply), parsed
    return parsed


def _machine(done: DoneReply, name: str) -> dict[str, Any]:
    machines = cast("list[dict[str, Any]]", done.result["machines"])
    (found,) = [machine for machine in machines if machine["name"] == name]
    return found


def _stored(rig: HubRig, name: str) -> str | None:
    with rig.open_store() as store, store.read() as transaction:
        machine_id = machine_id_by_name(transaction, name)
        assert machine_id is not None
        found = get_machine_runs(transaction, machine_id)
    return None if found is None else found.document


@pytest.fixture
def rig(tmp_path: Path) -> HubRig:
    return build_rig(tmp_path)


def test_beta_sees_alphas_paused_run_under_alpha(rig: HubRig) -> None:
    _status(rig, ALPHA_TOKEN, RunsDocument(open_runs=(_paused_run(),)))

    done = _status(rig, BETA_TOKEN, RunsDocument(), call_id="call-2")

    alpha = _machine(done, "alpha")
    (line,) = alpha["runs"]
    assert line["run_id"] == "run-a1"
    assert line["pipeline"] == "p6-implement"
    assert line["status"] == "paused"
    assert line["directory"] == "/work/alpha-core"
    assert line["checkpoint"]["paused_at"] == PAUSED_AT
    assert alpha["runs_reported_at"] is not None
    assert alpha["runs_problem"] is None
    beta = _machine(done, "beta")
    assert beta["runs"] == []
    assert beta["runs_reported_at"] is None
    assert done.result["hub_door_version"] is not None


def test_list_with_no_subject_stores_the_report_too(rig: HubRig) -> None:
    _status(
        rig,
        ALPHA_TOKEN,
        RunsDocument(open_runs=(_paused_run(),)),
        name="list",
    )

    assert _stored(rig, "alpha") is not None


def test_a_machine_that_stored_nothing_has_no_document(rig: HubRig) -> None:
    done = _status(rig, ALPHA_TOKEN, RunsDocument())

    assert _stored(rig, "beta") is None
    assert _machine(done, "beta")["runs_reported_at"] is None


def test_a_waiting_question_on_alpha_is_other_machine_for_beta(rig: HubRig) -> None:
    with rig.open_store() as store:
        machine = rig.machine(ALPHA_TOKEN)
        assert machine is not None
        store.act_as(machine)
        with store.write() as transaction:
            insert_question(
                transaction,
                run_id="run-a1",
                paused_at=PAUSED_AT,
                member_id=CORE,
                question="Ship?",
                checkout="/work/alpha-core",
                state=QuestionState.WAITING_ON_PM,
                answering_run_id=None,
                waiting_reason=None,
                claimed_at=NOW,
                updated_at=NOW,
            )

    done = _status(rig, BETA_TOKEN, RunsDocument())

    programs = cast("list[dict[str, Any]]", done.result["programs"])
    waiting = [
        entry
        for program in programs
        for member in program["members"]
        for entry in member["waiting_on_pm"]
    ]
    (entry,) = waiting
    assert entry["run_state"] == "other_machine"
    assert entry["machine"] == "alpha"
    assert entry["next"] is None


def test_a_bad_stored_document_is_a_problem_and_is_replaced_by_its_machine(
    rig: HubRig,
) -> None:
    _status(rig, ALPHA_TOKEN, RunsDocument(open_runs=(_paused_run(),)))
    with rig.open_store() as store, store.write() as transaction:
        transaction.execute(
            "UPDATE machine_runs SET document = ?", ('{"open_runs": "nope"}',)
        )

    seen = _status(rig, BETA_TOKEN, RunsDocument(), call_id="call-2")

    alpha = _machine(seen, "alpha")
    assert alpha["runs"] == []
    assert "open_runs" in alpha["runs_problem"]
    _status(rig, ALPHA_TOKEN, RunsDocument(), call_id="call-3")
    again = _status(rig, BETA_TOKEN, RunsDocument(), call_id="call-4")
    assert _machine(again, "alpha")["runs_problem"] is None


def test_a_call_whose_own_document_does_not_parse_stores_nothing(
    rig: HubRig,
) -> None:
    reply = rig.call(
        "status",
        {},
        token=ALPHA_TOKEN,
        extra={"here": CALLER, "runs": {"open_runs": "nope"}},
    )

    parsed = result_of(reply)
    assert isinstance(parsed, RefusedReply)
    assert parsed.code is RefusalCode.MALFORMED_CALL
    assert _stored(rig, "alpha") is None


def test_beta_closes_nothing_on_alpha(rig: HubRig) -> None:
    with rig.open_store() as store:
        machine = rig.machine(ALPHA_TOKEN)
        assert machine is not None
        store.act_as(machine)
        with store.write() as transaction:
            insert_question(
                transaction,
                run_id="run-a1",
                paused_at=PAUSED_AT,
                member_id=CORE,
                question="Ship?",
                checkout="/work/alpha-core",
                state=QuestionState.WAITING_ON_PM,
                answering_run_id=None,
                waiting_reason=None,
                claimed_at=NOW,
                updated_at=NOW,
            )

    done = _status(rig, BETA_TOKEN, RunsDocument())

    assert done.result["closed_now"] == []
    (row,) = rig.rows("SELECT state FROM questions")
    assert row[0] == QuestionState.WAITING_ON_PM.value


def test_a_failing_write_fails_the_call_and_stores_nothing(rig: HubRig) -> None:
    with rig.open_store() as store, store.write() as transaction:
        transaction.execute(
            "CREATE TRIGGER no_runs BEFORE INSERT ON machine_runs "
            "BEGIN SELECT RAISE(ABORT, 'full'); END"
        )

    reply = rig.call(
        "status",
        {},
        token=ALPHA_TOKEN,
        extra={"here": CALLER, "runs": runs_to_document(RunsDocument())},
    )

    parsed = result_of(reply)
    assert not isinstance(parsed, DoneReply), parsed
    assert rig.rows("SELECT COUNT(*) FROM machine_runs") == [(0,)]


def _put_session(
    rig: HubRig, token: str, session_id: str, started_minutes_ago: int, door: int
) -> None:
    machine = rig.machine(token)
    assert machine is not None
    with rig.open_store() as store:
        store.act_as(machine)
        with store.write() as transaction:
            upsert_session(
                transaction,
                Session(
                    session_id=session_id,
                    member_id=CORE,
                    client="claude-code",
                    directory=f"/work/{session_id}",
                    started_at=rig.clock() - timedelta(minutes=started_minutes_ago),
                    heartbeat_at=rig.clock() - timedelta(seconds=5),
                    push_confirmed_at=None,
                    client_version="0.2.3",
                    door_version=door,
                ),
            )


def test_sessions_of_two_machines_show_oldest_first_with_behind(rig: HubRig) -> None:
    _put_session(rig, ALPHA_TOKEN, "s-alpha", 5, DOOR_VERSION)
    _put_session(rig, BETA_TOKEN, "s-beta", 30, DOOR_VERSION + 1)

    done = _status(rig, ALPHA_TOKEN, RunsDocument())

    programs = cast("list[dict[str, Any]]", done.result["programs"])
    sessions = [
        entry
        for program in programs
        for member in program["members"]
        for entry in member["sessions"]
    ]
    assert [(s["machine"], s["behind"]) for s in sessions] == [
        ("beta", True),
        ("alpha", False),
    ]
    assert sessions[0]["door_version"] == DOOR_VERSION + 1
    assert sessions[0]["client_version"] == "0.2.3"


def test_machines_are_behind_true_false_or_null(rig: HubRig) -> None:
    with rig.open_store() as store, store.write() as transaction:
        transaction.execute(
            "UPDATE machines SET door_version = ? WHERE name = 'beta'",
            (DOOR_VERSION - 1,),
        )

    seen = _status(rig, ALPHA_TOKEN, RunsDocument())

    assert _machine(seen, "alpha")["behind"] is False
    assert _machine(seen, "beta")["behind"] is True
    with rig.open_store() as store, store.write() as transaction:
        transaction.execute(
            "UPDATE machines SET door_version = NULL WHERE name = 'beta'"
        )
    unknown = _status(rig, ALPHA_TOKEN, RunsDocument(), call_id="call-2")
    assert _machine(unknown, "beta")["behind"] is None


def test_list_document_equals_the_status_document(rig: HubRig) -> None:
    _put_session(rig, BETA_TOKEN, "s-beta", 30, DOOR_VERSION)

    listed = _status(rig, ALPHA_TOKEN, RunsDocument(), name="list")
    status = _status(rig, ALPHA_TOKEN, RunsDocument(), call_id="call-2")

    listed_status = cast("dict[str, Any]", listed.result.get("status", listed.result))
    assert listed_status["machines"] == status.result["machines"]
    assert listed_status["programs"] == status.result["programs"]
    assert listed_status["hub_door_version"] == DOOR_VERSION
