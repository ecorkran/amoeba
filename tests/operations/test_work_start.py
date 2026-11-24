"""``start_claimed`` and ``resume-run``: each kind started detached, each failure
recorded where its kind records it (slice 262, 6.4)."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from amoeba.amoeba_script import AmoebaScriptMissing
from amoeba.client.errors import HubUnreachableError
from amoeba.operations.processes import WaitableChild
from amoeba.operations.resume_run import run_resume
from amoeba.operations.steps.model_base import Step, StepModel
from amoeba.operations.steps.models_work import (
    HandlePauseItem,
    ResumeItem,
    WakeItem,
)
from amoeba.operations.work_start import (
    HANDLE_PAUSE_LOG_DIRECTORY,
    RESUME_RUN_LOG_DIRECTORY,
    START_FAILED_OUTCOME,
    start_claimed,
)
from amoeba.store.answers import get_answer
from amoeba.store.vocabulary import ResumeOutcome, WakeOutcome
from amoeba.store.wakes import get_wake
from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.launch import LaunchError
from operations.pause_support import DepsRig, FakeChild, build_deps
from operations.work_support import (
    PAUSE_LIMIT,
    Rig,
    answered_question,
    claimed_row,
    open_rig,
    wakeable_member,
)

SCRIPT = Path("/installed/bin/amoeba")
CHECKOUT = Path("/work/a")


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    opened = open_rig(tmp_path / "amoeba.sqlite3")
    yield opened
    opened.store.close()


def _deps(
    tmp_path: Path,
    script: Callable[[], Path] = lambda: SCRIPT,
    results: Sequence[LaunchError] | None = None,
) -> DepsRig:
    spawns: list[WaitableChild | LaunchError] = (
        [FakeChild(0)] if results is None else list(results)
    )
    built = build_deps(tmp_path, polls={}, spawns=spawns)
    built.deps = replace(built.deps, amoeba_script=script)
    return built


def _claimed_items(rig: Rig) -> tuple[ResumeItem, HandlePauseItem, WakeItem]:
    answered_question(rig, 1)
    claimed_row(rig, 2)
    wakeable_member(rig)
    rig.advance(PAUSE_LIMIT)
    items = rig.claim().items
    resume = next(item for item in items if isinstance(item, ResumeItem))
    pause = next(item for item in items if isinstance(item, HandlePauseItem))
    wake = next(item for item in items if isinstance(item, WakeItem))
    return resume, pause, wake


def test_each_kind_is_started_with_its_argv_directory_and_logs(
    tmp_path: Path, rig: Rig
) -> None:
    resume, pause, wake = _claimed_items(rig)
    deps = _deps(tmp_path)

    start_claimed(rig.steps(), deps.deps, [resume, pause, wake])

    first, second, third = deps.spawner.calls
    assert first.argv == (
        str(SCRIPT), "resume-run", str(resume.answer_seq), resume.claim_id
    )  # fmt: skip
    assert first.cwd == deps.deps.logs_dir.parent
    assert first.logs.stdout.parent == deps.deps.logs_dir / RESUME_RUN_LOG_DIRECTORY
    assert first.logs.stdout.name.startswith(f"{resume.answer_seq}-")
    assert first.logs.stderr.name.endswith(".stderr.log")
    assert second.argv == (str(SCRIPT), "handle-pause", "--json", "--", pause.run_id)
    assert second.cwd == Path(pause.checkout)
    assert second.logs.stdout.parent == deps.deps.logs_dir / HANDLE_PAUSE_LOG_DIRECTORY
    assert third.argv == (str(SCRIPT), "wake-run", wake.wake_id)
    assert third.cwd == Path(wake.directory)
    assert third.logs.stdout == Path(f"{wake.log_stem}.stdout.log")


def test_a_failed_start_is_recorded_as_each_kind_records_it(
    tmp_path: Path, rig: Rig
) -> None:
    resume, pause, wake = _claimed_items(rig)
    error = LaunchError(LaunchFailure.SPAWN_ERROR, "cannot start")
    deps = _deps(tmp_path, results=[error])

    start_claimed(rig.steps(), deps.deps, [resume, pause, wake])

    with rig.store.read() as transaction:
        answer = get_answer(transaction, resume.answer_seq)
        woke = get_wake(transaction, wake.wake_id)
    assert answer is not None
    assert (answer.resume_outcome, answer.resume_detail) == (
        ResumeOutcome.REFUSED,
        "cannot start",
    )
    assert woke is not None and woke.outcome is WakeOutcome.START_FAILED
    lines = [
        json.loads(line)
        for day in deps.deps.calls_log_dir.glob("*.jsonl")
        for line in day.read_text().splitlines()
    ]
    (line,) = lines
    assert line["outcome"] == START_FAILED_OUTCOME
    assert line["run_id"] == pause.run_id
    assert line["detail"] == "cannot start"


def test_a_missing_script_is_recorded_for_every_item_and_raises_nothing(
    tmp_path: Path, rig: Rig
) -> None:
    resume, pause, wake = _claimed_items(rig)

    def missing() -> Path:
        raise AmoebaScriptMissing("the amoeba script is not at /nowhere")

    deps = _deps(tmp_path, script=missing)

    start_claimed(rig.steps(), deps.deps, [resume, pause, wake])

    assert deps.spawner.calls == []
    with rig.store.read() as transaction:
        answer = get_answer(transaction, resume.answer_seq)
        woke = get_wake(transaction, wake.wake_id)
    assert answer is not None and answer.resume_outcome is ResumeOutcome.REFUSED
    assert woke is not None and woke.outcome is WakeOutcome.START_FAILED


class _DeadHub:
    """``Steps`` whose hub never answers."""

    def run[Request: StepModel, Reply: StepModel](
        self, step: Step[Request, Reply], request: Request
    ) -> Reply:
        raise HubUnreachableError("no reply")


def test_a_failed_start_that_cannot_be_recorded_still_raises_nothing(
    tmp_path: Path, rig: Rig
) -> None:
    resume, pause, wake = _claimed_items(rig)
    error = LaunchError(LaunchFailure.SPAWN_ERROR, "cannot start")
    deps = _deps(tmp_path, results=[error])

    start_claimed(_DeadHub(), deps.deps, [resume, pause, wake])

    assert len(deps.spawner.calls) == 3


def test_resume_run_with_a_claim_id_that_is_no_longer_the_answers_starts_nothing(
    tmp_path: Path, rig: Rig
) -> None:
    seq = answered_question(rig, 1)
    deps = _deps(tmp_path)

    result = run_resume(rig.steps(), deps.deps, seq, "a-claim-that-ran-out")

    assert result is None
    assert deps.spawner.calls == []
