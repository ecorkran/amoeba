"""``status`` closes open questions whose run has moved on or is gone
(slice 228, D4, D12, 7.7)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from functools import partial
from pathlib import Path

import pytest
from fake_sq import FakeListing, write_fake_sq
from store.decision_support import CORE, LINT, seed_programs
from store.question_support import NOW, claimed_question, waiting_question
from user_configs import user_config

from amoeba.operations.members import ContextForgeError
from amoeba.operations.resume import resume_bound_seconds
from amoeba.operations.status import StatusResult, status
from amoeba.store.answers import add_pm_answer, latest_answer
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_list import (
    ListedCheckpoint,
    ListedRun,
    RunListProblem,
    list_runs,
)
from operations.status_support import FakeCf, status_deps

NAMES = {CORE: "core-name", LINT: "lint-name"}
CONFIG = user_config()
BOUND = timedelta(seconds=resume_bound_seconds(CONFIG))
PAUSED_AT = "2026-11-09T08:00:00+00:00"
WAITING = QuestionKey("moved-run", PAUSED_AT)
GONE = QuestionKey("gone-run", PAUSED_AT)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3", busy_timeout_seconds=0.2) as opened:
        seed_programs(opened)
        yield opened


@pytest.fixture
def core_dir(tmp_path: Path) -> Path:
    path = tmp_path / "core"
    path.mkdir()
    return path


def _listed(
    run_id: str, run_status: str, directory: Path, paused_at: str | None = None
):
    checkpoint = (
        None
        if paused_at is None
        else ListedCheckpoint("agent_question", paused_at, "Which?")
    )
    return ListedRun(run_id, "asks_question", run_status, directory, checkpoint)


def _listing_json(directory: Path) -> str:
    """A listing with a running and a completed run, both in ``directory``."""
    entries = [
        {
            "run_id": run_id,
            "pipeline": "asks_question",
            "status": run_status,
            "working_directory": str(directory),
            "checkpoint": None,
        }
        for run_id, run_status in (("live-run", "running"), ("done-run", "completed"))
    ]
    return json.dumps(entries)


def _status(
    store: Store, tmp_path: Path, core_dir: Path, runs: list[ListedRun] | RunListProblem
) -> StatusResult:
    cf = FakeCf({core_dir: CORE})
    deps = status_deps(tmp_path, cf=cf, runs=runs, names=NAMES)
    return status(store, CONFIG, {}, directory=core_dir, deps=deps)


def _waiting(store: Store, key: QuestionKey) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(key, member_id=CORE), now=NOW)


def _row(store: Store, key: QuestionKey) -> QuestionRecord:
    with store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None
    return row


def test_a_waiting_row_whose_run_completed_or_is_unknown_closes_once(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _waiting(store, WAITING)
    _waiting(store, GONE)
    runs = [_listed(WAITING.run_id, "completed", core_dir)]

    first = _status(store, tmp_path, core_dir, runs)

    by_run = {entry.run_id: entry for entry in first.closed_now}
    assert by_run[WAITING.run_id].closed_reason is ClosedReason.RUN_MOVED_ON
    assert by_run[WAITING.run_id].closed_detail == "completed"
    assert by_run[GONE.run_id].closed_reason is ClosedReason.RUN_GONE
    assert len(first.closed_now) == 2
    assert by_run[WAITING.run_id].program == "trading"
    assert by_run[WAITING.run_id].member.name == "core-name"
    assert by_run[WAITING.run_id].question == waiting_question().question
    assert first.programs[0].members[0].waiting_on_pm == ()
    assert first.sweep_problem is None
    assert _row(store, WAITING).state is QuestionState.CLOSED

    second = _status(store, tmp_path, core_dir, runs)

    assert second.closed_now == ()


def test_a_run_paused_later_is_moved_on_and_one_at_the_pause_is_left(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _waiting(store, WAITING)
    here = QuestionKey("here-run", PAUSED_AT)
    _waiting(store, here)
    runs = [
        _listed(WAITING.run_id, "paused", core_dir, "2026-11-10T09:00:00+00:00"),
        _listed(here.run_id, "paused", core_dir, PAUSED_AT),
    ]

    result = _status(store, tmp_path, core_dir, runs)

    (closed,) = result.closed_now
    assert closed.run_id == WAITING.run_id
    assert closed.closed_detail == "paused at 2026-11-10T09:00:00+00:00"
    (still,) = result.programs[0].members[0].waiting_on_pm
    assert still.run_id == here.run_id


def test_a_young_claim_and_an_answer_whose_resume_may_be_in_flight_stay_open(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(WAITING, member_id=CORE), now=NOW)
    _waiting(store, GONE)
    with store.write() as transaction:
        add_pm_answer(transaction, GONE, "an answer", now=NOW)

    result = _status(store, tmp_path, core_dir, [])  # neither run is listed

    assert result.closed_now == ()
    assert _row(store, WAITING).state is QuestionState.CLAIMED
    assert _row(store, GONE).state is QuestionState.ANSWERED


def test_an_old_unresumed_answer_is_marked_not_delivered_and_reported(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _waiting(store, WAITING)
    with store.write() as transaction:
        seq = add_pm_answer(transaction, WAITING, "answer", now=NOW - 2 * BOUND)
    runs = [_listed(WAITING.run_id, "completed", core_dir)]

    result = _status(store, tmp_path, core_dir, runs)

    (entry,) = result.closed_now
    assert entry.answer_seq == seq
    assert entry.resume_outcome is ResumeOutcome.NOT_DELIVERED
    assert entry.closed_reason is None
    assert entry.closed_detail == "completed"
    with store.read() as transaction:
        answer = latest_answer(transaction, WAITING)
    assert answer is not None
    assert answer.resume_outcome is ResumeOutcome.NOT_DELIVERED


def test_a_run_absent_from_the_listing_but_with_a_run_file_stays_open(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _waiting(store, GONE)
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / f"{GONE.run_id}.json").write_text("{}", encoding="utf-8")

    result = _status(store, tmp_path, core_dir, [])

    assert result.closed_now == ()
    (still,) = result.programs[0].members[0].waiting_on_pm
    assert still.run_id == GONE.run_id
    assert _row(store, GONE).state is QuestionState.WAITING_ON_PM


@pytest.mark.parametrize(
    "problem", [RunListProblem("`sq runs list` did not finish"), RunListProblem("bad")]
)
def test_a_listing_failure_raises_as_before_and_closes_nothing(
    store: Store, tmp_path: Path, core_dir: Path, problem: RunListProblem
) -> None:
    _waiting(store, GONE)

    with pytest.raises(SquadronError):
        _status(store, tmp_path, core_dir, problem)

    assert _row(store, GONE).state is QuestionState.WAITING_ON_PM


def test_a_failed_sweep_write_shows_everything_before_the_sweep_and_the_problem(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _waiting(store, WAITING)
    holder = sqlite3.connect(store.path, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        result = _status(
            store, tmp_path, core_dir, [_listed(WAITING.run_id, "completed", core_dir)]
        )
    finally:
        holder.close()

    assert result.sweep_problem is not None
    assert result.closed_now == ()
    (shown,) = result.programs[0].members[0].waiting_on_pm
    assert shown.run_id == WAITING.run_id
    assert shown.run_state.value == "moved_on"
    assert _row(store, WAITING).state is QuestionState.WAITING_ON_PM


def test_a_names_failure_raises_before_the_sweep_closes_anything(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _waiting(store, WAITING)
    deps = status_deps(
        tmp_path,
        cf=FakeCf({core_dir: CORE}),
        runs=[_listed(WAITING.run_id, "completed", core_dir)],
        names=CfCallFailed("cf is down"),
    )

    with pytest.raises(ContextForgeError, match="cf is down"):
        status(store, CONFIG, {}, directory=core_dir, deps=deps)

    assert _row(store, WAITING).state is QuestionState.WAITING_ON_PM


def test_status_makes_one_listing_call_and_asks_for_all(
    store: Store,
    tmp_path: Path,
    core_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = write_fake_sq(
        tmp_path / "bin",
        waits={},
        run_exit_code=0,
        run_stderr="",
        runs_list=FakeListing(stdout=_listing_json(core_dir), stderr="", exit_code=0),
    )
    monkeypatch.setenv("PATH", f"{fake.directory}:/usr/bin:/bin")
    deps = status_deps(tmp_path, cf=FakeCf({core_dir: CORE}), runs=[], names=NAMES)
    deps = replace(deps, list_runs=partial(list_runs, timeout_seconds=30))

    status(store, CONFIG, {}, directory=core_dir, deps=deps)

    assert fake.list_calls() == [["runs", "list", "--json", "--all"]]
