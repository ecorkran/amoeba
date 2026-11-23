"""Waking in ``status`` and ``list`` (slice 244, D9)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from process_containment import contained_popen
from store.decision_support import CORE, LINT, seed_programs
from store.wake_support import COMMAND, claim
from store_open import open_local_store
from user_configs import user_config

from amoeba.cli.render.waiting import NOTHING_NEEDS_YOU, render_waiting
from amoeba.operations.deps import Deps
from amoeba.operations.list_view import ListResult
from amoeba.operations.status import StatusResult
from amoeba.operations.status_models import MemberStatus, WakeStatus
from amoeba.operations.wake_run import run_wake
from amoeba.store.store import Store
from amoeba.store.vocabulary import WakeOutcome
from amoeba.store.wakes import finish_wake
from operations.list_support import ListCf, project_entry
from operations.release_support import SettableClock
from operations.status_placed import list_view, status
from operations.status_support import CfAnswer, status_deps

ELSEWHERE = Path("/work/elsewhere")
PROJECTS = [project_entry(CORE, "core-name"), project_entry(LINT, "lint-name")]
CONFIG = user_config().model_copy(update={"max_wakes_per_day": 3})
TIMEOUT = timedelta(seconds=600)
HOUR = timedelta(hours=1)
SECRET_MARKER = "SECRET-MARKER-IN-A-COMMAND"
PID = 4242


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        _set_command(opened, COMMAND)
        yield opened


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def deps(tmp_path: Path, clock: SettableClock) -> Deps:
    cf = ListCf(PROJECTS, {ELSEWHERE: CfAnswer.NOT_A_PROJECT})
    base = status_deps(tmp_path, cf=cf, runs=[])
    return replace(base, clock=clock)


def _set_command(store: Store, command: str | None) -> None:
    with store.write() as transaction:
        transaction.execute(
            "UPDATE members SET wake_command = ? WHERE project_id = ?",
            (command, CORE),
        )


def _status(store: Store, deps: Deps) -> StatusResult:
    return status(store, CONFIG, {}, directory=ELSEWHERE, deps=deps)


def _core(store: Store, deps: Deps) -> MemberStatus:
    members = {m.member.id: m for p in _status(store, deps).programs for m in p.members}
    return members[CORE]


def _wake(store: Store, deps: Deps) -> WakeStatus:
    wake = _core(store, deps).wake
    assert wake is not None
    return wake


def _claim(store: Store, wake_id: str, clock: SettableClock) -> None:
    with store.write() as transaction:
        claimed = claim(
            transaction, wake_id, member_id=CORE, now=clock.now, max_wakes=100
        )
        assert claimed is not None


def _finish(
    store: Store,
    wake_id: str,
    clock: SettableClock,
    outcome: WakeOutcome,
    exit_code: int | None = None,
    detail: str | None = None,
) -> None:
    with store.write() as transaction:
        assert finish_wake(transaction, wake_id, outcome, exit_code, detail, clock.now)


def test_a_member_without_a_command_has_no_wake(store: Store, deps: Deps) -> None:
    _set_command(store, None)

    assert _core(store, deps).wake is None


def test_a_member_with_a_command_and_no_wakes_shows_only_the_command(
    store: Store, deps: Deps
) -> None:
    wake = _core(store, deps).wake

    assert wake is not None
    assert wake.command == COMMAND
    assert (wake.running, wake.stopped, wake.last_problem) == (None, None, None)


def test_a_live_row_is_running_and_not_overdue(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _claim(store, "w1", clock)
    clock.now += TIMEOUT - timedelta(seconds=1)

    running = _wake(store, deps).running

    assert running is not None
    assert running.overdue is False
    assert running.deadline_at == clock.now + timedelta(seconds=1)


def test_a_row_past_its_deadline_is_running_and_overdue_with_pid_and_log(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    started = clock.now
    _claim(store, "w1", clock)
    with store.write() as transaction:
        transaction.execute("UPDATE wakes SET command_pid = ?", (PID,))
    clock.now = started + TIMEOUT

    running = _wake(store, deps).running

    assert running is not None
    assert running.overdue is True
    assert running.command_pid == PID
    assert running.log_stem is not None
    assert running.log_stem.endswith("w1")
    # It is not live, so the member can be claimed again beside the old command.
    with store.write() as transaction:
        again = claim(transaction, "w2", member_id=CORE, now=clock.now, max_wakes=100)
    assert again is not None


def test_at_the_limit_stopped_has_the_counts_and_below_it_is_null(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    for index in range(2):
        _claim(store, f"w{index}", clock)
        _finish(store, f"w{index}", clock, WakeOutcome.EXITED, 0)
        clock.now += HOUR
    assert _wake(store, deps).stopped is None

    _claim(store, "w2", clock)
    _finish(store, "w2", clock, WakeOutcome.EXITED, 0)

    stopped = _wake(store, deps).stopped
    assert stopped is not None
    assert (stopped.used, stopped.limit) == (3, CONFIG.max_wakes_per_day)


@pytest.mark.parametrize(
    ("outcome", "exit_code", "detail"),
    [
        (WakeOutcome.START_FAILED, None, "FileNotFoundError: No such file"),
        (WakeOutcome.TIMED_OUT, None, None),
        (WakeOutcome.WRAPPER_FAILED, None, "RuntimeError"),
        (WakeOutcome.EXITED, 3, None),
    ],
)
def test_each_problem_outcome_is_the_last_problem(
    store: Store,
    deps: Deps,
    clock: SettableClock,
    outcome: WakeOutcome,
    exit_code: int | None,
    detail: str | None,
) -> None:
    _claim(store, "w1", clock)
    _finish(store, "w1", clock, outcome, exit_code, detail)

    problem = _wake(store, deps).last_problem

    assert problem is not None
    assert (problem.outcome, problem.exit_code, problem.detail) == (
        outcome,
        exit_code,
        detail,
    )
    assert problem.ended_at == clock.now


def test_a_clean_exit_is_not_a_problem(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _claim(store, "w1", clock)
    _finish(store, "w1", clock, WakeOutcome.EXITED, 0)

    assert _wake(store, deps).last_problem is None


def test_the_newest_ended_row_decides_and_a_clean_exit_clears_an_older_failure(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _claim(store, "failed", clock)
    _finish(store, "failed", clock, WakeOutcome.TIMED_OUT)
    clock.now += HOUR
    _claim(store, "clean", clock)
    _finish(store, "clean", clock, WakeOutcome.EXITED, 0)

    assert _wake(store, deps).last_problem is None

    clock.now += HOUR
    _claim(store, "newer-failure", clock)
    _finish(store, "newer-failure", clock, WakeOutcome.EXITED, 2)
    problem = _wake(store, deps).last_problem
    assert problem is not None
    assert problem.exit_code == 2


def test_list_json_equals_status_and_a_running_wake_leaves_nothing_needs_you(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _claim(store, "w1", clock)

    listed = list_view(store, CONFIG, {}, directory=ELSEWHERE, deps=deps)
    expected = _status(store, deps)

    assert isinstance(listed, ListResult)
    assert listed.document() == expected.model_dump(mode="json")
    assert expected.notice is None
    assert NOTHING_NEEDS_YOU in render_waiting(expected, now=clock.now)


def test_no_command_text_reaches_the_document_beyond_the_command_field(
    tmp_path: Path, store: Store, deps: Deps, clock: SettableClock
) -> None:
    command = f"/nonexistent/{SECRET_MARKER}-agent --flag"
    _set_command(store, command)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    with store.write() as transaction:
        claimed = claim(
            transaction,
            "w1",
            member_id=CORE,
            now=clock.now,
            directory=str(checkout),
        )
    assert claimed is not None

    outcome = run_wake(store, deps, "w1", popen=contained_popen)

    assert outcome is WakeOutcome.START_FAILED
    document = json.dumps(_status(store, deps).model_dump(mode="json"))
    assert document.count(SECRET_MARKER) == 1
    wake = _wake(store, deps)
    assert SECRET_MARKER in wake.command
    assert wake.last_problem is not None
    assert wake.last_problem.detail == "FileNotFoundError: No such file or directory"
