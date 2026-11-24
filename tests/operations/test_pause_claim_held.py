"""``start_held_claim``: a held question whose request is done (slice 242, D6, 4.3)."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from amoeba.answering.values import AnsweredBy, DeclineReason
from amoeba.operations.answering_run import scratch_path
from amoeba.operations.pause_claim import (
    HeldRequest,
    held_request_of,
    start_held_claim,
)
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    SkipReason,
)
from amoeba.operations.processes import WaitableChild
from amoeba.operations.steps.models_pause import PauseBeginReply
from amoeba.operations.steps.pause import request_facts
from amoeba.store.answers import answers_of
from amoeba.store.models import QuestionRecord
from amoeba.store.question_closing import dismiss_question
from amoeba.store.questions import (
    get_question,
)
from amoeba.store.vocabulary import QuestionState, RequestState, ResumeOutcome
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs
from amoeba.upstream.squadron.run_outcome import RunPoll
from operations.handle_rig import (
    KEY,
    PAUSE,
    RUNNING_DOC,
    World,
    world,
)
from operations.held_support import (
    REQUEST_ID,
    RESULT,
    RESULT_VERSION,
    add_addressee,
    automatic_answers_to_the_limit,
    begin_for,
    hold,
    seed_request,
    steps_for,
    target_of,
)
from operations.pause_support import START

#: A direct call skips eligibility's poll: the resume's first look, then running.
DIRECT_POLLS = (PAUSE, RUNNING_DOC)


def _record(w: World) -> QuestionRecord:
    with w.store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    return record


def _done_request(w: World) -> HeldRequest:
    add_addressee(w.store)
    message = seed_request(w.store, RequestState.DONE)
    with w.store.read() as transaction:
        facts = request_facts(transaction, message.message_id, w.deps.clock())
    assert facts.held is not None
    return held_request_of(facts.held)


def _claim(
    w: World, request: HeldRequest, begun: PauseBeginReply | None = None
) -> HandlePauseResult:
    begun = begin_for(w) if begun is None else begun
    return start_held_claim(steps_for(w), w.deps, target_of(w), begun, request)


def test_a_done_request_is_claimed_answered_from_its_passage_and_resumed(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=DIRECT_POLLS) as w:
        request = _done_request(w)
        hold(w)

        result = _claim(w, request)

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert result.request_id == REQUEST_ID
        record = _record(w)
        assert record.state is QuestionState.ANSWERED
        assert record.request_id == REQUEST_ID
        assert record.answering_run_id == result.answering_run_id
        (answering,) = w.spawned.answering
        assert str(record.answering_run_id) in answering
        scratch = scratch_path(w.deps.answering_dir, str(record.answering_run_id))
        passages = (scratch / "passages.md").read_text(encoding="utf-8")
        assert "kind: request_result" in passages
        assert RESULT in passages
        assert f"version: {RESULT_VERSION}" in passages
        with w.store.read() as transaction:
            (answer,) = answers_of(transaction, KEY)
        assert answer.answered_by is AnsweredBy.ANSWERER
        assert answer.resume_outcome is ResumeOutcome.RESUMED


def test_at_the_answer_limit_the_held_question_waits_and_starts_nothing(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=DIRECT_POLLS) as w:
        request = _done_request(w)
        automatic_answers_to_the_limit(w)
        hold(w)

        result = _claim(w, request)

        assert result.outcome is HandlePauseOutcome.WAITING_ON_PM
        assert result.waiting_reason is DeclineReason.ANSWER_LIMIT_REACHED
        assert result.request_id == REQUEST_ID
        assert w.spawned.argvs == []
        record = _record(w)
        assert record.state is QuestionState.WAITING_ON_PM
        assert record.waiting_reason is DeclineReason.ANSWER_LIMIT_REACHED
        assert record.claimed_at == START


def test_a_sources_problem_waits_with_its_reason(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=DIRECT_POLLS, params={"slice": "299"}) as w:
        request = _done_request(w)
        hold(w)

        result = _claim(w, request)

        assert result.waiting_reason is DeclineReason.SOURCES_MISSING
        assert _record(w).state is QuestionState.WAITING_ON_PM
        assert w.spawned.argvs == []


def test_a_scratch_failure_waits_as_answering_launch_failed(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    with world(tmp_path, paused_polls=DIRECT_POLLS) as w:
        w.deps = replace(w.deps, answering_dir=blocker / "answering")
        request = _done_request(w)
        hold(w)

        result = _claim(w, request)

        assert result.waiting_reason is DeclineReason.ANSWERING_LAUNCH_FAILED
        assert _record(w).waiting_reason is DeclineReason.ANSWERING_LAUNCH_FAILED
        assert w.spawned.argvs == []


def test_a_second_call_after_the_claim_is_already_claimed(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=DIRECT_POLLS) as w:
        request = _done_request(w)
        hold(w)
        # Both calls read the held row before either claims it.
        begun = begin_for(w)
        second_calls: list[HandlePauseResult] = []
        real_spawn = w.deps.spawn

        def second_call_during_the_run(
            argv: Sequence[str], cwd: Path, logs: LaunchLogs
        ) -> WaitableChild | LaunchError:
            if not second_calls and "--resume" not in argv:
                second_calls.append(_claim(w, request, begun))
            return real_spawn(argv, cwd, logs)

        w.deps = replace(w.deps, spawn=second_call_during_the_run)

        first = _claim(w, request, begun)

        (second,) = second_calls
        assert second.outcome is HandlePauseOutcome.SKIPPED
        assert second.skip_reason is SkipReason.ALREADY_CLAIMED
        assert first.outcome is HandlePauseOutcome.RESUMED
        assert len(w.spawned.answering) == 1


def test_a_row_dismissed_before_the_claim_is_superseded_and_its_scratch_gone(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=DIRECT_POLLS) as w:
        request = _done_request(w)
        hold(w)
        real_cf = w.deps.cf_run
        dismissed = {"done": False}

        def dismiss_meanwhile(
            argv: Sequence[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if argv[:3] == ["cf", "config", "get"] and not dismissed["done"]:
                dismissed["done"] = True
                with w.store.write() as transaction:
                    current = get_question(transaction, KEY)
                    assert current is not None
                    assert dismiss_question(transaction, current, "no", now=START)
            return real_cf(argv, **kwargs)

        w.deps = replace(w.deps, cf_run=dismiss_meanwhile)

        result = _claim(w, request)

        assert dismissed["done"]
        assert result.outcome is HandlePauseOutcome.SUPERSEDED
        assert result.request_id == REQUEST_ID
        assert w.spawned.argvs == []
        assert _record(w).state is QuestionState.CLOSED
        scratch_root = w.deps.answering_dir
        assert not scratch_root.exists() or list(scratch_root.iterdir()) == []


def test_no_transaction_is_open_during_the_answering_and_resume_runs(
    tmp_path: Path,
) -> None:
    writes: list[str] = []

    with world(tmp_path, paused_polls=DIRECT_POLLS) as w:

        def take_a_write(run_id: str) -> None:
            with w.store.write():
                writes.append(run_id)

        request = _done_request(w)
        hold(w)
        real_spawn = w.deps.spawn
        real_poll = w.deps.poll_run

        def spawn_after_a_write(
            argv: Sequence[str], cwd: Path, logs: LaunchLogs
        ) -> WaitableChild | LaunchError:
            take_a_write("spawn")
            return real_spawn(argv, cwd, logs)

        def poll_after_a_write(run_id: str) -> RunPoll:
            take_a_write(run_id)
            return real_poll(run_id)

        w.deps = replace(w.deps, spawn=spawn_after_a_write, poll_run=poll_after_a_write)

        result = _claim(w, request)

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert writes.count("spawn") == 2  # the answering run and the resume
        assert len(writes) > 2
