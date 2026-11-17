"""``handle_pause`` for a question no row exists for (slice 223, tasks 7.5, 7.7)."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import DEFAULT_WORKTREE
from store.question_support import NOW
from user_configs import user_config

from amoeba.answering.values import AnsweredBy, AnsweringEvidence, DeclineReason
from amoeba.operations.answering_run import PAUSE_COMMAND_OPT_OUT_FLAG
from amoeba.operations.deps import Deps
from amoeba.operations.names import OperationName
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    SkipReason,
)
from amoeba.operations.processes import Spawner, WaitableChild
from amoeba.operations.request_release import MAX_STARTS_PER_CALL
from amoeba.operations.rm import rm
from amoeba.operations.set_up_models import SetUpOutcome
from amoeba.store.answers import add_pm_answer, answers_of, settle_answered
from amoeba.store.held_questions import HeldQuestion, insert_held
from amoeba.store.message_transitions import MEMBER_REMOVED_REASON
from amoeba.store.models import AnswerRecord, QuestionKey, QuestionRecord
from amoeba.store.questions import NewQuestion, get_question, insert_question
from amoeba.store.vocabulary import QuestionState, RequestState, ResumeOutcome
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs
from amoeba.upstream.squadron.run_outcome import PollFailure
from amoeba.wiring_release import start_after
from operations.handle_rig import (
    ANSWER_TEXT,
    CHECK_NO,
    HAPPY_PAUSED_POLLS,
    KEY,
    OTHER_PAUSE,
    PAUSE,
    PAUSED_AT,
    PROJECT_ID,
    QUESTION,
    RUNNING_DOC,
    World,
    world,
)
from operations.held_support import ADDRESSEE, REQUEST_ID, add_addressee, seed_request
from operations.pause_support import FakeChild, SpawnRecorder
from operations.set_up_support import DIRECTORY, FakeCf


def _record(w: World) -> QuestionRecord:
    with w.store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    return record


def _answers(w: World) -> tuple[AnswerRecord, ...]:
    with w.store.read() as transaction:
        return answers_of(transaction, KEY)


def _waiting(result: HandlePauseResult, reason: DeclineReason) -> None:
    assert result.outcome is HandlePauseOutcome.WAITING_ON_PM, result
    assert result.waiting_reason is reason, result


def _claimed(key: QuestionKey, run_id: str) -> NewQuestion:
    return NewQuestion(
        key=key,
        member_id=PROJECT_ID,
        question="q",
        checkout="/c",
        slice_label=None,
        source_commit=None,
        passages=None,
        answering_run_id=run_id,
        waiting_reason=None,
        waiting_detail=None,
    )


# 7.5: the claim step


def _earlier_automatic_answers(w: World) -> list[QuestionKey]:
    """As many settled automatic answers for the run as its limit allows."""
    keys: list[QuestionKey] = []
    for number in range(w.config.answer_limit):
        earlier = QuestionKey(KEY.run_id, f"2026-11-09T0{number}:00:00+00:00")
        with w.store.write() as transaction:
            insert_question(
                transaction, _claimed(earlier, f"earlier-{number}"), now=NOW
            )
        settle_answered(
            w.store,
            earlier,
            f"earlier-{number}",
            answer="x",
            cited=(),
            evidence=AnsweringEvidence(),
            gate=lambda _prior: None,
            now=NOW,
        )
        keys.append(earlier)
    return keys


def test_an_answer_limit_already_met_waits_and_starts_nothing(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _earlier_automatic_answers(w)

        result = w.handle()

        _waiting(result, DeclineReason.ANSWER_LIMIT_REACHED)
        assert w.spawned.argvs == []
        record = _record(w)
        assert record.state is QuestionState.WAITING_ON_PM
        assert record.answering_run_id is None


def test_a_pm_answer_gives_a_run_at_its_limit_another_automatic_answer(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        earlier = _earlier_automatic_answers(w)
        with w.store.write() as transaction:
            add_pm_answer(
                transaction, earlier[-1], "the PM stepped in", now=NOW, via=None
            )

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        (answer,) = _answers(w)
        assert answer.answered_by is AnsweredBy.ANSWERER


def test_a_context_failure_waits_with_its_reason_and_starts_nothing(
    tmp_path: Path,
) -> None:
    with world(tmp_path, params={"slice": "299"}) as w:
        result = w.handle()

        _waiting(result, DeclineReason.SOURCES_MISSING)
        assert "299" in (result.detail or "")
        assert w.spawned.argvs == []
        record = _record(w)
        assert record.state is QuestionState.WAITING_ON_PM
        assert record.waiting_reason is DeclineReason.SOURCES_MISSING
        assert record.answering_run_id is None


def test_a_scratch_that_cannot_be_made_waits_as_answering_launch_failed(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    with world(tmp_path) as w:
        w.deps = replace(w.deps, answering_dir=blocker / "answering")

        result = w.handle()

        _waiting(result, DeclineReason.ANSWERING_LAUNCH_FAILED)
        assert w.spawned.argvs == []
        record = _record(w)
        assert record.answering_run_id is None
        assert record.slice_label is not None  # the context was gathered before


def test_a_lost_insert_race_removes_the_scratch_and_skips(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        raced = {"done": False}
        real_cf = w.deps.cf_run

        def another_claimant_wins(
            argv: Sequence[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if argv[:3] == ["cf", "config", "get"] and not raced["done"]:
                raced["done"] = True
                with w.store.write() as transaction:
                    insert_question(
                        transaction, _claimed(KEY, "someone-elses"), now=NOW
                    )
            return real_cf(argv, **kwargs)

        w.deps = replace(w.deps, cf_run=another_claimant_wins)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.SKIPPED
        assert result.skip_reason is SkipReason.ALREADY_CLAIMED
        assert w.spawned.argvs == []
        assert _record(w).answering_run_id == "someone-elses"
        scratch_root = w.deps.answering_dir
        assert not scratch_root.exists() or list(scratch_root.iterdir()) == []


# 7.7: the answer step


def test_a_question_is_answered_and_the_run_resumed_end_to_end(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert result.key == KEY
        assert result.checkout == str(w.directory)
        record = _record(w)
        assert record.state is QuestionState.ANSWERED
        assert record.question == QUESTION
        assert record.slice_label == "none"
        assert record.passages
        assert record.evidence is not None
        assert record.evidence.verdict == "yes"
        (answer,) = _answers(w)
        assert answer.answered_by is AnsweredBy.ANSWERER
        assert answer.answer == ANSWER_TEXT
        assert answer.cited == ("P1",)
        assert answer.resume_outcome is ResumeOutcome.RESUMED
        assert answer.resume_log is not None
        assert result.answer_seq == answer.seq
        assert result.answering_run_id == record.answering_run_id
        (answering,) = w.spawned.answering
        assert answering.count(PAUSE_COMMAND_OPT_OUT_FLAG) == 1
        assert "--run-id" in answering
        (resume,) = w.spawned.resumes
        assert resume[-1] == f"You asked: {QUESTION}\nAnswer: {ANSWER_TEXT}"
        assert w.spawned.cwds[-1] == w.directory


def test_the_answering_run_runs_in_a_scratch_holding_the_members_inputs(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        w.handle()

        scratch = w.spawned.cwds[0]
        assert scratch.parent == w.deps.answering_dir
        assert (scratch / "question.md").read_text(encoding="utf-8").endswith(QUESTION)
        assert "slice: none" in (scratch / "question.md").read_text(encoding="utf-8")
        assert "kind: rule" in (scratch / "passages.md").read_text(encoding="utf-8")
        barred = (scratch / "not_authorized.md").read_text(encoding="utf-8")
        assert "merge_to_main" in barred and "push" in barred
        assert "deploy" not in barred  # not denied by default, and not denied here


def test_an_answer_the_check_rejects_waits_and_is_not_resumed(tmp_path: Path) -> None:
    with world(tmp_path, check=CHECK_NO) as w:
        result = w.handle()

        _waiting(result, DeclineReason.CHECK_SAID_NO)
        assert w.spawned.resumes == []
        assert _record(w).state is QuestionState.WAITING_ON_PM
        assert _answers(w) == ()


def test_a_pm_answer_during_the_answering_run_supersedes_and_is_not_resumed(
    tmp_path: Path,
) -> None:
    pm_answered = {"done": False}

    def pm_answers_meanwhile(run_id: str) -> None:
        if run_id.startswith("amoeba-") and not pm_answered["done"]:
            pm_answered["done"] = True
            with w.store.write() as transaction:
                add_pm_answer(transaction, KEY, "PM says 250.", now=NOW, via=None)

    with world(tmp_path, on_poll=pm_answers_meanwhile) as w:
        result = w.handle()

        assert result.outcome is HandlePauseOutcome.SUPERSEDED, result
        assert w.spawned.resumes == []
        assert [a.answered_by for a in _answers(w)] == [AnsweredBy.PM]


def test_a_refused_resume_is_reported_and_recorded_as_refused(tmp_path: Path) -> None:
    # The run never leaves the pause: the resume child stays alive until it is stopped.
    stuck = (PAUSE, PAUSE, PAUSE)
    with world(tmp_path, paused_polls=stuck) as w:
        result = w.handle()

        assert result.outcome is HandlePauseOutcome.REFUSED, result
        assert "not running after" in (result.detail or "")
        (answer,) = _answers(w)
        assert answer.resume_outcome is ResumeOutcome.REFUSED


def test_a_run_that_moved_on_before_the_resume_is_not_delivered(tmp_path: Path) -> None:
    moved = (PAUSE, OTHER_PAUSE)
    with world(tmp_path, paused_polls=moved) as w:
        result = w.handle()

        assert result.outcome is HandlePauseOutcome.NOT_DELIVERED, result
        assert w.spawned.resumes == []
        assert _answers(w)[0].resume_outcome is ResumeOutcome.NOT_DELIVERED


def test_a_pause_with_a_slice_parameter_answers_with_the_slice_label(
    tmp_path: Path,
) -> None:
    roomy = user_config().model_copy(update={"passages_max_chars": 500_000})
    with world(tmp_path, params={"slice": "132"}, config=roomy) as w:
        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert _record(w).slice_label == "132 Pipeline Supervisor"
        passages = (w.spawned.cwds[0] / "passages.md").read_text(encoding="utf-8")
        assert "kind: plan" in passages


def test_a_second_call_after_a_resume_is_settled(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=(*HAPPY_PAUSED_POLLS, PAUSE, RUNNING_DOC)) as w:
        first = w.handle()
        second = w.handle()

        assert first.outcome is HandlePauseOutcome.RESUMED
        assert second.outcome is HandlePauseOutcome.SKIPPED
        assert second.skip_reason is SkipReason.SETTLED
        assert len(w.spawned.answering) == 1


# Slice 242, 6.5: held questions started after an operation, and by handle_pause


ADDRESSEE_NAME = "addressee-name"
MARKED_PAUSE = PAUSE.model_copy(
    update={
        "checkpoint": PAUSE.checkpoint.model_copy(
            update={"question": f"{QUESTION}\namoeba-request: {REQUEST_ID}"}
        )
        if PAUSE.checkpoint is not None
        else None
    }
)


def _child_runs_handle_pause(w: World) -> SpawnRecorder:
    """A spawner that plays the detached child: it runs ``handle_pause`` in-process."""
    played: list[HandlePauseResult] = []

    def run_the_child() -> None:
        played.append(w.handle())

    recorder = SpawnRecorder([FakeChild(0)], on_spawn=run_the_child)
    w.deps = replace(w.deps, amoeba_script=lambda: Path("/bin/amoeba"))
    w.deps = replace(w.deps, spawn=_spawn_or_resume(w.deps, recorder))
    return recorder


def _spawn_or_resume(deps: Deps, recorder: SpawnRecorder) -> Spawner:
    """Starts of ``handle-pause`` go to ``recorder``; everything else (answering runs
    and resumes) to the world's own spawner."""
    world_spawn = deps.spawn

    def spawn(
        argv: Sequence[str], cwd: Path, logs: LaunchLogs
    ) -> WaitableChild | LaunchError:
        if "handle-pause" in argv:
            return recorder(argv, cwd, logs)
        return world_spawn(argv, cwd, logs)

    return spawn


def test_rm_of_the_addressee_releases_the_held_question_to_the_pm(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=(MARKED_PAUSE,)) as w:
        add_addressee(w.store)
        seed_request(w.store, RequestState.OPEN)
        assert w.handle().outcome is HandlePauseOutcome.HELD
        recorder = _child_runs_handle_pause(w)
        removed = rm(
            w.store,
            w.config,
            {"members": [ADDRESSEE_NAME]},
            directory=DIRECTORY,
            run=FakeCf(
                directory_fixture=DEFAULT_WORKTREE,
                projects=[(ADDRESSEE, ADDRESSEE_NAME)],
            ),
        )
        assert removed.outcome is SetUpOutcome.APPLIED

        start_after(OperationName.RM, w.store, lambda: w.config, lambda: w.deps)

        assert len(recorder.calls) == 1
        record = _record(w)
        assert record.state is QuestionState.WAITING_ON_PM
        assert record.waiting_reason is DeclineReason.REQUEST_CANCELLED
        assert record.waiting_detail == MEMBER_REMOVED_REASON


def test_handle_pause_starts_ended_held_questions_and_a_large_batch_drains(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        add_addressee(w.store)
        count = MAX_STARTS_PER_CALL + 2
        for number in range(count):
            request_id = f"ended-{number}"
            seed_request(w.store, RequestState.DECLINED, request_id=request_id)
            held = HeldQuestion(
                QuestionKey(f"other-run-{number}", PAUSED_AT), PROJECT_ID, "q", "/c"
            )
            with w.store.write() as transaction:
                insert_held(transaction, held, request_id, NOW)
        recorder = SpawnRecorder([FakeChild(0)])
        w.deps = replace(
            w.deps,
            amoeba_script=lambda: Path("/bin/amoeba"),
            spawn=_spawn_or_resume(w.deps, recorder),
        )

        w.handle()
        first_round = len(recorder.calls)
        w.handle()

        assert first_round == MAX_STARTS_PER_CALL
        started = {call.argv[-1] for call in recorder.calls}
        assert started == {f"other-run-{number}" for number in range(count)}


def _sq_not_answering(run_id: str) -> PollFailure:
    return PollFailure(f"sq is not answering for {run_id}")


def test_a_handle_pause_that_raises_still_starts_ended_held_questions(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        add_addressee(w.store)
        seed_request(w.store, RequestState.DECLINED, request_id="ended")
        held = HeldQuestion(QuestionKey("other-run", PAUSED_AT), PROJECT_ID, "q", "/c")
        with w.store.write() as transaction:
            insert_held(transaction, held, "ended", NOW)
        recorder = SpawnRecorder([FakeChild(0)])
        w.deps = replace(
            w.deps,
            amoeba_script=lambda: Path("/bin/amoeba"),
            spawn=_spawn_or_resume(w.deps, recorder),
            poll_run=_sq_not_answering,
        )

        with pytest.raises(SquadronError, match="sq is not answering"):
            w.handle()

        assert [call.argv[-1] for call in recorder.calls] == ["other-run"]
