"""Every branch of the shared resume with injected poller and spawner
(slice 223, task 6.2). The recordings are real ``sq`` 0.24.25 output."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from pathlib import Path

import pytest
from fake_sq import (
    COMPLETED,
    LOCK_BEFORE,
    LOCK_REFUSED_STDOUT,
    PAUSED_AGENT_QUESTION,
    RUNNING,
    SQUADRON_FIXTURES,
    poll_result,
    write_fake_sq,
)
from process_containment import contained_popen
from store.question_support import MEMBER_ID, NOW, seed_members

from amoeba.answering.values import AnsweredBy
from amoeba.operations.pause_models import ResumeResult
from amoeba.operations.processes import WaitableChild, start_child
from amoeba.operations.resume import RESUME_POLL_INTERVAL_SECONDS, resume
from amoeba.store.answers import add_pm_answer, answers_of, record_resume
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.questions import NewQuestion, get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ResumeOutcome
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs
from amoeba.upstream.squadron.run_outcome import PollFailure, RunPoll
from operations.pause_support import DepsRig, FakeChild, build_deps

RUN = "demo-run"
WAIT = 5.0
PAUSE = poll_result(PAUSED_AGENT_QUESTION, RUN)
assert PAUSE.checkpoint is not None
PAUSED_AT = PAUSE.checkpoint.paused_at_text or ""
RUNNING_DOC = poll_result(RUNNING, RUN)
COMPLETED_DOC = poll_result(COMPLETED, RUN)
OTHER_PAUSE = poll_result(LOCK_BEFORE, RUN)
ANSWER_TEXT = "The limit is 300 lines."
KEY = QuestionKey(RUN, PAUSED_AT)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _question(store: Store) -> tuple[QuestionRecord, int]:
    new = NewQuestion(
        key=KEY,
        member_id=MEMBER_ID,
        question="…What is the maximum length of a source file?",
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
        seq = add_pm_answer(transaction, KEY, ANSWER_TEXT, now=NOW)
    with store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    return record, seq


def _stored(store: Store, seq: int) -> tuple[ResumeOutcome | None, str | None]:
    with store.read() as transaction:
        row = next(r for r in answers_of(transaction, KEY) if r.seq == seq)
    return row.resume_outcome, row.resume_detail


def _run(  # noqa: PLR0913 - the fixtures a resume test varies
    tmp_path: Path,
    store: Store,
    polls: Sequence[RunPoll],
    children: Sequence[WaitableChild | LaunchError] = (),
    *,
    on_spawn: Callable[[], None] | None = None,
    on_poll: Callable[[], None] | None = None,
) -> tuple[ResumeResult, DepsRig, int]:
    question, seq = _question(store)
    rig = build_deps(
        tmp_path,
        polls={RUN: polls},
        spawns=list(children),
        on_spawn=on_spawn,
        on_poll=on_poll,
    )
    result = resume(store, question, seq, deps=rig.deps, wait_seconds=WAIT)
    return result, rig, seq


def test_a_run_that_is_not_paused_is_not_delivered_and_nothing_starts(
    tmp_path: Path, store: Store
) -> None:
    result, rig, seq = _run(tmp_path, store, [RUNNING_DOC])

    assert result.outcome is ResumeOutcome.NOT_DELIVERED
    assert "already running" in (result.detail or "")
    assert rig.spawner.calls == []
    assert _stored(store, seq)[0] is ResumeOutcome.NOT_DELIVERED


def test_a_different_paused_at_is_not_delivered(tmp_path: Path, store: Store) -> None:
    result, rig, _ = _run(tmp_path, store, [OTHER_PAUSE])

    assert result.outcome is ResumeOutcome.NOT_DELIVERED
    assert "no longer at this pause" in (result.detail or "")
    assert rig.spawner.calls == []


def test_a_completed_run_is_not_delivered(tmp_path: Path, store: Store) -> None:
    result, _, _ = _run(tmp_path, store, [COMPLETED_DOC])

    assert result.outcome is ResumeOutcome.NOT_DELIVERED


def test_a_run_seen_running_is_resumed_with_the_logs_recorded(
    tmp_path: Path, store: Store
) -> None:
    result, rig, seq = _run(
        tmp_path, store, [PAUSE, RUNNING_DOC], [FakeChild(exit_code=None)]
    )

    assert result.outcome is ResumeOutcome.RESUMED
    assert result.detail is None
    (call,) = rig.spawner.calls
    assert call.cwd == Path("/work/a")
    assert result.resume_log == str(call.logs.stdout)
    assert call.logs.stdout.parent == tmp_path / "logs" / "resume" / RUN
    assert call.logs.stdout.name.startswith(f"{seq}-")
    assert call.logs.stdout.name.endswith(".stdout.log")
    assert _stored(store, seq) == (ResumeOutcome.RESUMED, None)
    with store.read() as transaction:
        recorded = next(iter(answers_of(transaction, KEY)))
    assert recorded.resume_log == result.resume_log
    assert recorded.resume_at == NOW


def test_a_run_that_moved_past_the_pause_is_resumed(
    tmp_path: Path, store: Store
) -> None:
    result, _, _ = _run(tmp_path, store, [PAUSE, COMPLETED_DOC], [FakeChild(0)])

    assert result.outcome is ResumeOutcome.RESUMED


def test_a_run_that_paused_again_before_a_poll_saw_running_is_resumed(
    tmp_path: Path, store: Store
) -> None:
    result, _, _ = _run(tmp_path, store, [PAUSE, OTHER_PAUSE], [FakeChild(3)])

    assert result.outcome is ResumeOutcome.RESUMED


def test_a_child_gone_with_the_run_still_at_the_pause_is_refused_with_its_message(
    tmp_path: Path, store: Store
) -> None:
    message = (SQUADRON_FIXTURES / LOCK_REFUSED_STDOUT).read_text(encoding="utf-8")

    def refusing_spawner(
        argv: Sequence[str], cwd: Path, logs: LaunchLogs
    ) -> WaitableChild | LaunchError:
        logs.stdout.parent.mkdir(parents=True, exist_ok=True)
        logs.stdout.write_text(message, encoding="utf-8")  # the real lock message
        logs.stderr.write_text("", encoding="utf-8")  # and the real empty stderr
        return FakeChild(exit_code=1)  # the real exit code

    question, seq = _question(store)
    rig = build_deps(
        tmp_path, polls={RUN: [PAUSE, PAUSE]}, spawns=[], spawner=refusing_spawner
    )

    result = resume(store, question, seq, deps=rig.deps, wait_seconds=WAIT)

    assert result.outcome is ResumeOutcome.REFUSED
    assert result.detail == message.strip()
    assert "still running under pid" in (result.detail or "")
    assert _stored(store, seq) == (ResumeOutcome.REFUSED, message.strip())


def test_a_timeout_with_the_run_still_paused_is_refused_after_the_kill(
    tmp_path: Path, store: Store
) -> None:
    result, rig, _ = _run(tmp_path, store, [PAUSE], [FakeChild(exit_code=None)])

    assert result.outcome is ResumeOutcome.REFUSED
    assert result.detail == "not running after 5 seconds"
    assert rig.sleep.calls
    assert set(rig.sleep.calls) == {RESUME_POLL_INTERVAL_SECONDS}
    assert sum(rig.sleep.calls) >= WAIT


def test_a_timeout_then_running_after_the_kill_is_resumed_with_a_note(
    tmp_path: Path, store: Store
) -> None:
    # The polls say paused until the group stop; only the poll after it says running.
    stopped = {"yes": False}

    class _Child(FakeChild):
        def wait(self, timeout: float | None = None) -> int:
            stopped["yes"] = stopped["yes"] or timeout is None
            return super().wait(timeout)

    def poll(run_id: str) -> RunPoll:
        del run_id
        return RUNNING_DOC if stopped["yes"] else PAUSE

    question, seq = _question(store)
    rig = build_deps(tmp_path, polls={RUN: [PAUSE]}, spawns=[_Child(exit_code=None)])
    deps = replace(rig.deps, poll_run=poll)

    result = resume(store, question, seq, deps=deps, wait_seconds=WAIT)

    assert result.outcome is ResumeOutcome.RESUMED
    assert result.detail == "resume process terminated after taking the run"


def test_a_spawn_error_is_refused(tmp_path: Path, store: Store) -> None:
    error = LaunchError(LaunchFailure.SPAWN_ERROR, "OSError: no sq")

    result, _, seq = _run(tmp_path, store, [PAUSE], [error])

    assert result.outcome is ResumeOutcome.REFUSED
    assert "no sq" in (result.detail or "")
    assert result.resume_log is None
    assert _stored(store, seq)[0] is ResumeOutcome.REFUSED


def test_an_unreadable_first_poll_raises_and_writes_nothing(
    tmp_path: Path, store: Store
) -> None:
    question, seq = _question(store)
    rig = build_deps(tmp_path, polls={RUN: [PollFailure("sq broke")]}, spawns=[])

    with pytest.raises(SquadronError, match="sq broke"):
        resume(store, question, seq, deps=rig.deps, wait_seconds=WAIT)

    assert _stored(store, seq) == (None, None)
    assert rig.spawner.calls == []


def test_an_answer_of_another_question_is_a_programming_error(
    tmp_path: Path, store: Store
) -> None:
    question, _ = _question(store)
    other = QuestionKey(RUN, "2026-11-10T13:00:00+00:00")
    with store.write() as transaction:
        insert_question(
            transaction,
            NewQuestion(
                key=other,
                member_id=MEMBER_ID,
                question="q",
                checkout="/c",
                slice_label=None,
                source_commit=None,
                passages=None,
                answering_run_id="a-2",
                waiting_reason=None,
                waiting_detail=None,
            ),
            now=NOW,
        )
        foreign = add_pm_answer(transaction, other, "x", now=NOW)
    rig = build_deps(tmp_path, polls={RUN: [PAUSE]}, spawns=[])

    with pytest.raises(ValueError, match="not an answer"):
        resume(store, question, foreign, deps=rig.deps, wait_seconds=WAIT)


def test_resumed_and_not_delivered_are_never_overwritten(
    tmp_path: Path, store: Store
) -> None:
    result, _, seq = _run(tmp_path, store, [PAUSE, RUNNING_DOC], [FakeChild(None)])
    assert result.outcome is ResumeOutcome.RESUMED
    question, _ = _question_unchanged(store)

    # A second resume of the same answer meets the run already running.
    again = build_deps(tmp_path / "again", polls={RUN: [RUNNING_DOC]}, spawns=[])
    second = resume(store, question, seq, deps=again.deps, wait_seconds=WAIT)

    assert second.outcome is ResumeOutcome.NOT_DELIVERED
    assert _stored(store, seq)[0] is ResumeOutcome.RESUMED
    with store.write() as transaction:
        assert not record_resume(
            transaction, seq, ResumeOutcome.REFUSED, detail="late", log=None, at=NOW
        )


def _question_unchanged(store: Store) -> tuple[QuestionRecord, int]:
    with store.read() as transaction:
        record = get_question(transaction, KEY)
        answer = next(iter(answers_of(transaction, KEY)))
    assert record is not None
    assert answer.answered_by is AnsweredBy.PM
    return record, answer.seq


def test_a_refused_resume_can_be_retried_and_the_retry_overwrites_it(
    tmp_path: Path, store: Store
) -> None:
    first, _, seq = _run(tmp_path, store, [PAUSE], [FakeChild(exit_code=None)])
    assert first.outcome is ResumeOutcome.REFUSED
    question, _ = _question_unchanged(store)
    retry = build_deps(
        tmp_path / "retry", polls={RUN: [PAUSE, RUNNING_DOC]}, spawns=[FakeChild(None)]
    )

    second = resume(store, question, seq, deps=retry.deps, wait_seconds=WAIT)

    assert second.outcome is ResumeOutcome.RESUMED
    assert _stored(store, seq)[0] is ResumeOutcome.RESUMED


def test_no_store_transaction_is_open_while_spawning_or_polling(
    tmp_path: Path, store: Store
) -> None:
    def store_is_free() -> None:
        with store.write():
            pass

    result, _, _ = _run(
        tmp_path,
        store,
        [PAUSE, RUNNING_DOC],
        [FakeChild(None)],
        on_spawn=store_is_free,
        on_poll=store_is_free,
    )

    assert result.outcome is ResumeOutcome.RESUMED


@pytest.mark.parametrize(
    "answer",
    [
        "plain",
        "has spaces and 'single' and \"double\" quotes",
        "…leading ellipsis, then; shell $chars `and` more",
        "two\nlines",
        "--decision accept --run-id other",
        "-- --instructions again",
    ],
)
def test_instructions_are_one_argv_element_holding_the_composed_text(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    fake = write_fake_sq(tmp_path / "bin", waits={}, run_exit_code=0, run_stderr="")
    monkeypatch.setenv("PATH", f"{fake.directory}:/usr/bin:/bin")
    children: list[WaitableChild] = []

    def real_spawner(
        argv: Sequence[str], cwd: Path, logs: LaunchLogs
    ) -> WaitableChild | LaunchError:
        started = start_child(argv, cwd, logs, popen=contained_popen)
        if not isinstance(started, LaunchError):
            children.append(started)
        return started

    new = NewQuestion(
        key=KEY,
        member_id=MEMBER_ID,
        question="…What limit?",
        checkout=str(tmp_path),
        slice_label=None,
        source_commit=None,
        passages=None,
        answering_run_id="a-1",
        waiting_reason=None,
        waiting_detail=None,
    )
    with store.write() as transaction:
        insert_question(transaction, new, now=NOW)
        seq = add_pm_answer(transaction, KEY, answer, now=NOW)
    with store.read() as transaction:
        question = get_question(transaction, KEY)
    assert question is not None
    rig = build_deps(
        tmp_path,
        polls={RUN: [PAUSE, RUNNING_DOC]},
        spawns=[],
        spawner=real_spawner,
    )

    result = resume(store, question, seq, deps=rig.deps, wait_seconds=WAIT)
    children[0].wait(timeout=20)  # the fake has written its record once it exits

    assert result.outcome is ResumeOutcome.RESUMED
    expected = f"You asked: …What limit?\nAnswer: {answer}"
    assert fake.run_calls() == [["run", "--resume", RUN, "--instructions", expected]]
