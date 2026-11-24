"""The attempt file and D6's table of what a later attempt does (slice 262)."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import replace
from pathlib import Path

import pytest
from fake_sq import (
    COMPLETED,
    LOCK_BEFORE,
    PAUSED_AGENT_QUESTION,
    RUNNING,
    poll_result,
)
from store.question_support import MEMBER_ID, NOW, seed_members
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.deps import Deps
from amoeba.operations.pause_models import ResumeResult
from amoeba.operations.pause_results import claim_and_resume
from amoeba.operations.processes import WaitableChild
from amoeba.operations.resume import EARLIER_ATTEMPT_DETAIL, ResumeUnreadableError
from amoeba.operations.resume_attempt import (
    attempt_path,
    read_attempt,
    write_judged,
    write_started,
)
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.limits import resume_claim_seconds
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.answers import add_pm_answer, answers_of
from amoeba.store.models import QuestionKey
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ResumeOutcome
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs
from amoeba.upstream.squadron.run_outcome import PollFailure, RunPoll
from operations.pause_support import DepsRig, FakeChild, build_deps

RUN = "demo-run"
CONFIG = user_config().model_copy(update={"resume_wait_seconds": 5.0})
PAUSE = poll_result(PAUSED_AGENT_QUESTION, RUN)
assert PAUSE.checkpoint is not None
KEY = QuestionKey(RUN, PAUSE.checkpoint.paused_at_text or "")
RUNNING_DOC = poll_result(RUNNING, RUN)
COMPLETED_DOC = poll_result(COMPLETED, RUN)
OTHER_PAUSE = poll_result(LOCK_BEFORE, RUN)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _answered(store: Store) -> int:
    new = NewQuestion(
        key=KEY,
        member_id=MEMBER_ID,
        question="…What is the limit?",
        checkout="/work/a",
        slice_label=None,
        source_commit=None,
        passages=None,
        answering_run_id="a-1",
        waiting_reason=None,
        waiting_detail=None,
    )
    with store.write() as transaction:
        insert_question(transaction, new, now=NOW)
        return add_pm_answer(transaction, KEY, "300 lines", now=NOW, via=None)


def _resume(store: Store, seq: int, rig: DepsRig) -> ResumeResult:
    steps = LocalSteps(store, StepEdges(rig.deps.clock, lambda: CONFIG))
    result = claim_and_resume(steps, seq, rig.deps)
    assert result is not None, "another attempt holds the resume claim"
    return result


def _stored(store: Store, seq: int) -> tuple[ResumeOutcome | None, str | None]:
    with store.read() as transaction:
        row = next(r for r in answers_of(transaction, KEY) if r.seq == seq)
    return row.resume_outcome, row.resume_detail


def _file(deps: Deps, seq: int) -> Path:
    return attempt_path(deps.logs_dir, RUN, seq)


def _rig(
    tmp_path: Path,
    polls: Sequence[RunPoll],
    spawns: Sequence[FakeChild] = (),
) -> DepsRig:
    return build_deps(tmp_path, polls={RUN: polls}, spawns=list(spawns))


def test_an_attempt_writes_started_then_the_judged_outcome(
    tmp_path: Path, store: Store
) -> None:
    seq = _answered(store)
    rig = _rig(tmp_path, [PAUSE, RUNNING_DOC], [FakeChild(None)])
    seen_started: list[bool] = []
    original = rig.spawner

    def spawn_and_look(
        argv: Sequence[str], cwd: Path, logs: LaunchLogs
    ) -> WaitableChild | LaunchError:
        found = read_attempt(_file(rig.deps, seq))
        seen_started.append(found is not None and found.is_started)
        return original(argv, cwd, logs)

    rig.deps = replace(rig.deps, spawn=spawn_and_look)

    _resume(store, seq, rig)

    assert seen_started == [True]
    judged = read_attempt(_file(rig.deps, seq))
    assert judged is not None
    assert judged.outcome is ResumeOutcome.RESUMED


@pytest.mark.parametrize("final", [ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED])
def test_a_final_outcome_in_the_file_is_recorded_with_no_poll_and_no_second_start(
    tmp_path: Path, store: Store, final: ResumeOutcome
) -> None:
    seq = _answered(store)
    rig = _rig(tmp_path, [])  # a poll would fail: there is nothing to return
    write_judged(_file(rig.deps, seq), final, "earlier", "/log")

    result = _resume(store, seq, rig)

    assert (result.outcome, result.detail, result.resume_log) == (
        final,
        "earlier",
        "/log",
    )
    assert rig.spawner.calls == []
    assert _stored(store, seq) == (final, "earlier")


def test_started_and_the_run_gone_from_the_pause_records_resumed_and_starts_nothing(
    tmp_path: Path, store: Store
) -> None:
    seq = _answered(store)
    rig = _rig(tmp_path, [RUNNING_DOC])
    write_started(_file(rig.deps, seq))

    result = _resume(store, seq, rig)

    assert result.outcome is ResumeOutcome.RESUMED
    assert result.detail == EARLIER_ATTEMPT_DETAIL
    assert rig.spawner.calls == []
    assert _stored(store, seq) == (ResumeOutcome.RESUMED, EARLIER_ATTEMPT_DETAIL)


def test_started_and_the_run_still_paused_starts_sq_again(
    tmp_path: Path, store: Store
) -> None:
    seq = _answered(store)
    rig = _rig(tmp_path, [PAUSE, RUNNING_DOC], [FakeChild(None)])
    write_started(_file(rig.deps, seq))

    result = _resume(store, seq, rig)

    assert result.outcome is ResumeOutcome.RESUMED
    assert len(rig.spawner.calls) == 1


def test_a_refused_in_the_file_is_never_replayed(tmp_path: Path, store: Store) -> None:
    seq = _answered(store)
    rig = _rig(tmp_path, [PAUSE, RUNNING_DOC], [FakeChild(None)])
    write_judged(_file(rig.deps, seq), ResumeOutcome.REFUSED, "earlier", None)

    result = _resume(store, seq, rig)

    assert result.outcome is ResumeOutcome.RESUMED
    assert len(rig.spawner.calls) == 1


def test_started_and_an_unreadable_first_poll_records_nothing_and_leaves_the_file(
    tmp_path: Path, store: Store
) -> None:
    seq = _answered(store)
    rig = _rig(tmp_path, [PollFailure("sq broke")])
    write_started(_file(rig.deps, seq))

    with pytest.raises(SquadronError, match="sq broke") as raised:
        _resume(store, seq, rig)

    assert not isinstance(raised.value, ResumeUnreadableError)
    assert _stored(store, seq) == (None, None)
    found = read_attempt(_file(rig.deps, seq))
    assert found is not None
    assert found.is_started

    # The claim runs out; the next attempt polls again and finds the run gone.
    rig.clock.advance(resume_claim_seconds(CONFIG))
    later = _rig(tmp_path / "later", [RUNNING_DOC])
    later.deps = replace(later.deps, clock=rig.clock, logs_dir=rig.deps.logs_dir)

    result = _resume(store, seq, later)

    assert result.outcome is ResumeOutcome.RESUMED
    assert _stored(store, seq)[0] is ResumeOutcome.RESUMED


def test_a_failed_attempt_file_write_is_logged_and_the_resume_still_records(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    seq = _answered(store)
    rig = _rig(tmp_path, [PAUSE, RUNNING_DOC], [FakeChild(None)])
    # A file where the run's directory should be: every write of the file fails.
    (rig.deps.logs_dir / "resume").mkdir(parents=True)
    (rig.deps.logs_dir / "resume" / RUN).write_text("in the way")

    with caplog.at_level(logging.ERROR):
        result = _resume(store, seq, rig)

    assert result.outcome is ResumeOutcome.RESUMED
    assert _stored(store, seq)[0] is ResumeOutcome.RESUMED
    assert "cannot write the resume attempt file" in caplog.text
