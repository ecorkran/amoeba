"""``status`` reads the ``runs`` document and no disk but the sweep's run-file check
(slice 261, 12.2, D11)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from store.decision_support import CORE, LINT, seed_programs
from store.question_support import NOW, waiting_question
from store.seed import insert_checkout
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations import status as status_module
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.runs_document import (
    LeftOut,
    OpenRun,
    RunsDocument,
    left_out_text,
)
from amoeba.operations.status_models import StatusResult
from amoeba.store.machines import ActingMachine, invite_machine, the_owner
from amoeba.store.models import QuestionKey
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState
from amoeba.upstream.squadron.errors import SquadronError
from operations.runs_doc_support import open_run, project
from operations.status_support import FakeCf, in_directory, recorded_run, status_deps

CONFIG = user_config()
PAUSED = "demo-pause-1"
RUNNING = "run-20261111-p6-fe470d63"
PAUSED_AT = "2026-11-09T08:00:00+00:00"
NOWHERE = HereNotAProject(not_a_project="none")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


def _status(
    store: Store, tmp_path: Path, runs: RunsDocument, here: HereCaller | None = None
) -> StatusResult:
    deps = status_deps(tmp_path, cf=FakeCf({}), runs=[])
    return status_module.status(
        store,
        CONFIG,
        {},
        here=here or NOWHERE,
        runs=runs,
        clock=deps.clock,
    )


def _run(run_id: str, project_id: str) -> OpenRun:
    return open_run(
        in_directory(recorded_run(run_id), Path("/work/anywhere")), project(project_id)
    )


def _run_ids(result: StatusResult, member: str) -> list[str]:
    return [
        run.run_id
        for program in result.programs
        for found in program.members
        if found.member.id == member
        for run in found.runs
    ]


def test_a_run_goes_under_the_member_whose_checkout_is_on_the_calling_machine(
    store: Store, tmp_path: Path
) -> None:
    result = _status(store, tmp_path, RunsDocument(open_runs=(_run(RUNNING, CORE),)))

    assert _run_ids(result, CORE) == [RUNNING]
    assert _run_ids(result, LINT) == []


def test_the_same_project_id_on_another_machine_is_not_placed(
    store: Store, tmp_path: Path
) -> None:
    with store.write() as transaction:
        invite_machine(transaction, "beta", "f" * 64, NOW)
        beta = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'beta'"
            ).fetchone()[0]
        )
        owner = the_owner(transaction)
        local = ActingMachine(
            int(
                transaction.execute(
                    "SELECT machine_id FROM machines WHERE name = 'local'"
                ).fetchone()[0]
            ),
            owner,
        )
    store.act_as(ActingMachine(beta, owner))
    with store.write() as transaction:
        insert_checkout(
            transaction,
            member_id=LINT,
            cf_project_id="cf-on-beta",
            path="/beta/lint",
            now=NOW,
        )
    store.act_as(local)

    result = _status(
        store, tmp_path, RunsDocument(open_runs=(_run(RUNNING, "cf-on-beta"),))
    )

    assert _run_ids(result, LINT) == []


def test_a_paused_run_whose_lookup_ran_out_of_time_is_unplaced(
    store: Store, tmp_path: Path
) -> None:
    ran_out = open_run(
        in_directory(recorded_run(PAUSED), Path("/work/anywhere")),
        project(CORE).model_copy(
            update={"kind": "failed", "project_id": None, "detail": "time ran out"}
        ),
    )

    result = _status(store, tmp_path, RunsDocument(open_runs=(ran_out,)))

    (unplaced,) = result.unplaced_runs
    assert (unplaced.run_id, unplaced.detail) == (PAUSED, "time ran out")


def test_left_out_runs_are_reported_in_file_problems(
    store: Store, tmp_path: Path
) -> None:
    left_out = LeftOut(paused=1, open=2, completed=3)

    result = _status(store, tmp_path, RunsDocument(left_out=left_out))

    expected = left_out_text(left_out)
    assert expected is not None
    assert expected in result.file_problems
    assert "1 paused, 2 other open, 3 completed" in expected


def test_a_listing_problem_raises_squadron_error(store: Store, tmp_path: Path) -> None:
    with pytest.raises(SquadronError, match="sq was not found"):
        _status(store, tmp_path, RunsDocument(listing_problem="sq was not found"))


def _waiting(store: Store, run_id: str) -> QuestionKey:
    key = QuestionKey(run_id, PAUSED_AT)
    with store.write() as transaction:
        insert_question(transaction, waiting_question(key, member_id=CORE), now=NOW)
    return key


def test_a_question_whose_run_was_cut_stays_open_unless_the_client_found_it_absent(
    store: Store, tmp_path: Path
) -> None:
    # The client found the run's file (it is in no ``absent_runs``): the hub reads no
    # disk and keeps the row open (262 D9).
    key = _waiting(store, "cut-run")

    result = _status(store, tmp_path, RunsDocument(left_out=LeftOut(completed=1)))

    assert result.closed_now == ()
    with store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None and row.state is QuestionState.WAITING_ON_PM


def test_a_question_whose_run_the_document_lacks_and_names_absent_is_gone(
    store: Store, tmp_path: Path
) -> None:
    _waiting(store, "vanished-run")

    result = _status(store, tmp_path, RunsDocument(absent_runs=("vanished-run",)))

    (closed,) = result.closed_now
    assert closed.closed_reason is ClosedReason.RUN_GONE
