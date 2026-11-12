"""The ``status`` operation end to end over fakes (slice 224, 3.8)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from store.decision_support import CORE, LINT, TOOLS, TRADING, seed_programs
from store.question_support import NOW, waiting_question
from user_configs import user_config

from amoeba.operations.members import ContextForgeError
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.status import StatusOutcome, StatusResult, status
from amoeba.operations.status_models import UnplacedReason, WaitingRunState
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_list import ListedRun, RunListProblem
from operations.status_support import (
    CfAnswer,
    FakeCf,
    in_directory,
    recorded_run,
    status_deps,
)

NAMES = {CORE: "core-name", LINT: "lint-name"}
PAUSED = "demo-pause-1"
PUSH = "demo-push-3"
RUNNING = "run-20261111-p6-fe470d63"
NULL_DIRECTORY_PAUSED = "run-20261105-p6-7dc230a3"
NULL_DIRECTORY_FAILED = "run-20261105-effort-compact-acbbe8e8"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


@pytest.fixture
def core_dir(tmp_path: Path) -> Path:
    path = tmp_path / "core"
    path.mkdir()
    return path


@pytest.fixture
def lint_dir(tmp_path: Path) -> Path:
    path = tmp_path / "lint"
    path.mkdir()
    return path


@pytest.fixture
def elsewhere(tmp_path: Path) -> Path:
    path = tmp_path / "elsewhere"
    path.mkdir()
    return path


def _run_status(
    store: Store,
    tmp_path: Path,
    cf: FakeCf,
    runs: list[ListedRun] | RunListProblem,
    *,
    directory: Path,
    document: object = None,
    names: dict[str, str] | CfCallFailed | None = None,
) -> StatusResult:
    deps = status_deps(
        tmp_path, cf=cf, runs=runs, names=NAMES if names is None else names
    )
    return status(
        store,
        user_config(),
        {} if document is None else document,
        directory=directory,
        deps=deps,
    )


def test_a_member_with_nothing_to_show_is_still_listed(
    store: Store, tmp_path: Path, core_dir: Path, elsewhere: Path
) -> None:
    cf = FakeCf({core_dir: CORE, elsewhere: CfAnswer.NOT_A_PROJECT})

    result = _run_status(store, tmp_path, cf, [], directory=core_dir)

    assert result.outcome is StatusOutcome.LISTED
    (program,) = result.programs
    assert program.program == TRADING
    (member,) = program.members
    assert (member.member.id, member.member.name) == (CORE, "core-name")
    assert member.runs == ()
    assert member.waiting_on_pm == ()
    assert result.unplaced_runs == ()


def test_two_members_in_different_programs_show_their_own_runs_under_every_program(
    store: Store, tmp_path: Path, core_dir: Path, lint_dir: Path, elsewhere: Path
) -> None:
    cf = FakeCf({core_dir: CORE, lint_dir: LINT, elsewhere: CfAnswer.NOT_A_PROJECT})
    runs = [
        in_directory(recorded_run(RUNNING), core_dir),
        in_directory(recorded_run(PUSH), lint_dir),
    ]

    result = _run_status(store, tmp_path, cf, runs, directory=elsewhere)

    assert [program.program for program in result.programs] == [TOOLS, TRADING]
    by_member = {
        member.member.id: member
        for program in result.programs
        for member in program.members
    }
    assert [run.run_id for run in by_member[CORE].runs] == [RUNNING]
    assert [run.run_id for run in by_member[LINT].runs] == [PUSH]
    assert by_member[LINT].runs[0].working_directory == lint_dir


def test_a_program_flag_narrows_the_scope(
    store: Store, tmp_path: Path, core_dir: Path, elsewhere: Path
) -> None:
    cf = FakeCf({core_dir: CORE, elsewhere: CfAnswer.NOT_A_PROJECT})

    result = _run_status(
        store, tmp_path, cf, [], directory=elsewhere, document={"program": TOOLS}
    )

    assert [program.program for program in result.programs] == [TOOLS]


def test_a_lookup_failure_is_unplaced_beside_a_waiting_question_still_shown(
    store: Store, tmp_path: Path, core_dir: Path, elsewhere: Path
) -> None:
    key = QuestionKey("gone-run", "2026-11-09T08:00:00+00:00")
    with store.write() as transaction:
        insert_question(transaction, waiting_question(key, member_id=CORE), now=NOW)
    broken = tmp_path / "broken"
    broken.mkdir()
    cf = FakeCf(
        {core_dir: CORE, broken: CfAnswer.FAILS, elsewhere: CfAnswer.NOT_A_PROJECT}
    )
    runs = [in_directory(recorded_run(PAUSED), broken)]

    result = _run_status(store, tmp_path, cf, runs, directory=core_dir)

    (entry,) = result.unplaced_runs
    assert entry.run_id == PAUSED
    assert entry.reason is UnplacedReason.LOOKUP_FAILED
    assert entry.detail is not None
    (member,) = result.programs[0].members
    (waiting,) = member.waiting_on_pm
    assert waiting.run_id == "gone-run"
    assert waiting.run_state is WaitingRunState.NOT_LISTED
    assert waiting.next is None


def test_unplaced_runs_are_paused_runs_with_their_checkpoint_kind(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    runs = [
        recorded_run(NULL_DIRECTORY_PAUSED),
        recorded_run(NULL_DIRECTORY_FAILED),
        recorded_run(RUNNING),
    ]
    cf = FakeCf({core_dir: CORE})

    result = _run_status(
        store,
        tmp_path,
        cf,
        [in_directory(run, None) for run in runs],
        directory=core_dir,
    )

    (entry,) = result.unplaced_runs
    assert entry.model_dump(mode="json") == {
        "run_id": NULL_DIRECTORY_PAUSED,
        "status": "paused",
        "reason": "no_directory",
        "checkpoint_kind": "awaits_human",
        "detail": None,
    }


def test_a_waiting_question_at_its_pause_names_answer_and_a_pm_flows_through(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    run = in_directory(recorded_run(PAUSED), core_dir)
    assert run.checkpoint is not None
    assert run.checkpoint.paused_at is not None
    key = QuestionKey(PAUSED, run.checkpoint.paused_at)
    with store.write() as transaction:
        insert_question(transaction, waiting_question(key, member_id=CORE), now=NOW)

    result = _run_status(
        store, tmp_path, FakeCf({core_dir: CORE}), [run], directory=core_dir
    )

    (member,) = result.programs[0].members
    (entry,) = member.runs
    assert entry.pause is PauseClass.WAITING_ON_PM
    (waiting,) = member.waiting_on_pm
    assert waiting.run_state is WaitingRunState.AT_PAUSE
    assert waiting.next is not None
    assert waiting.next.paused_at == run.checkpoint.paused_at


def test_an_sq_failure_raises_naming_the_command_and_status_needs(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    with pytest.raises(SquadronError, match=r"runs list --json.*boom"):
        _run_status(
            store,
            tmp_path,
            FakeCf({core_dir: CORE}),
            RunListProblem("boom"),
            directory=core_dir,
        )


def test_a_names_failure_raises(store: Store, tmp_path: Path, core_dir: Path) -> None:
    with pytest.raises(ContextForgeError, match="cf is down"):
        _run_status(
            store,
            tmp_path,
            FakeCf({core_dir: CORE}),
            [],
            directory=core_dir,
            names=CfCallFailed("cf is down"),
        )


def test_a_member_missing_from_the_names_raises(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    with pytest.raises(ContextForgeError, match=CORE):
        _run_status(
            store,
            tmp_path,
            FakeCf({core_dir: CORE}),
            [],
            directory=core_dir,
            names={LINT: "lint-name"},
        )


def test_an_unknown_program_is_rejected_with_the_known_ids(
    store: Store, tmp_path: Path, elsewhere: Path
) -> None:
    result = _run_status(
        store,
        tmp_path,
        FakeCf({}),
        [],
        directory=elsewhere,
        document={"program": "nope"},
    )

    assert result.outcome is StatusOutcome.REJECTED
    assert result.rejection is RejectCode.UNKNOWN_PROGRAM
    assert "tools, trading" in result.problems[0]
    assert result.programs == ()


@pytest.mark.parametrize("document", [{"programme": "x"}, {"program": ""}, 7])
def test_a_malformed_request_is_rejected(
    store: Store, tmp_path: Path, elsewhere: Path, document: object
) -> None:
    result = _run_status(
        store, tmp_path, FakeCf({}), [], directory=elsewhere, document=document
    )

    assert result.outcome is StatusOutcome.REJECTED
    assert result.rejection is RejectCode.MALFORMED


def test_no_store_transaction_is_open_while_sq_is_asked(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    def list_runs() -> list[ListedRun]:
        with store.write():  # fails if status still held a transaction open
            return []

    deps = status_deps(tmp_path, cf=FakeCf({core_dir: CORE}), runs=[], names=NAMES)
    deps = replace(deps, list_runs=list_runs)

    result = status(store, user_config(), {}, directory=core_dir, deps=deps)

    assert result.outcome is StatusOutcome.LISTED


def test_a_cf_lookup_that_times_out_is_unplaced_as_lookup_failed(
    store: Store, tmp_path: Path, core_dir: Path, elsewhere: Path
) -> None:
    slow = tmp_path / "slow"
    slow.mkdir()
    cf = FakeCf({core_dir: CORE, slow: CfAnswer.TIMES_OUT})
    runs = [in_directory(recorded_run(PAUSED), slow)]

    result = _run_status(store, tmp_path, cf, runs, directory=core_dir)

    (entry,) = result.unplaced_runs
    assert entry.reason is UnplacedReason.LOOKUP_FAILED
    assert entry.detail is not None
    assert "timed out" in entry.detail
