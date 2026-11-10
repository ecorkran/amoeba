"""``handle_pause`` for a question that already has a row: the settled paths and the
dead claim (slice 223, tasks 7.9, 7.11)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from functools import partial
from pathlib import Path

import pytest
from fake_sq import PAUSED_INTERACTIVE, poll_result
from store.question_support import PASSAGE

from amoeba.answering.values import AnsweredBy, AnsweringEvidence, DeclineReason
from amoeba.operations.answering_run import Claim, scratch_path
from amoeba.operations.answering_settle import Superseded, settle
from amoeba.operations.pause_models import HandlePauseOutcome, SkipReason
from amoeba.store.answers import Settled, add_pm_answer, answers_of, record_resume
from amoeba.store.models import AnswerRecord, QuestionRecord
from amoeba.store.questions import (
    NewQuestion,
    get_question,
    insert_question,
    settle_answered,
    settle_waiting,
)
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_outcome import (
    PollFailure,
    RunEnded,
    RunFailure,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
)
from operations.handle_rig import (
    ANSWER_TEXT,
    CHECK_YES,
    KEY,
    PROJECT_ID,
    PROPOSED,
    QUESTION,
    World,
    world,
)
from operations.pause_support import START

OLD_RUN = "amoeba-20261110T110000Z-oldoldoldold"
WAIT = 600.0


def _claim_row(w: World, *, age_seconds: float) -> None:
    """A ``claimed`` row for the paused question, claimed ``age_seconds`` ago."""
    new = NewQuestion(
        key=KEY,
        member_id=PROJECT_ID,
        question=QUESTION,
        checkout=str(w.directory),
        slice_label="none",
        source_commit="abc123",
        passages=(replace(PASSAGE, id="P1"),),
        answering_run_id=OLD_RUN,
        waiting_reason=None,
        waiting_detail=None,
    )
    with w.store.write() as transaction:
        insert_question(transaction, new, now=START - timedelta(seconds=age_seconds))


def _answered_row(w: World) -> int:
    """The row after an automatic answer: claimed, then ``answered``."""
    _claim_row(w, age_seconds=0)
    outcome = settle_answered(
        w.store,
        KEY,
        OLD_RUN,
        answer=ANSWER_TEXT,
        cited=("P1",),
        evidence=AnsweringEvidence(),
        gate=lambda _prior: None,
        now=START,
    )
    assert isinstance(outcome, Settled)
    return outcome.answer_seq


def _record(w: World) -> QuestionRecord:
    with w.store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    return record


def _answers(w: World) -> tuple[AnswerRecord, ...]:
    with w.store.read() as transaction:
        return answers_of(transaction, KEY)


def _ended(outcome: RunOutcome, run_id: str, **fields: object) -> RunOutcomeDocument:
    return RunOutcomeDocument.model_validate(
        {"run_id": run_id, "outcome": outcome.value, **fields}
    )


def _write_replies(w: World, run_id: str) -> None:
    scratch = scratch_path(w.deps.answering_dir, run_id)
    scratch.mkdir(parents=True)
    (scratch / "answer.json").write_text(json.dumps(PROPOSED), encoding="utf-8")
    (scratch / "check.json").write_text(json.dumps(CHECK_YES), encoding="utf-8")


# 7.9: settled-row paths


def test_an_answer_not_yet_handed_over_is_resumed_with_no_answering_run(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        seq = _answered_row(w)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert result.answer_seq == seq
        assert w.spawned.answering == []
        (resume,) = w.spawned.resumes
        assert resume[-1] == f"You asked: {QUESTION}\nAnswer: {ANSWER_TEXT}"
        assert _answers(w)[0].resume_outcome is ResumeOutcome.RESUMED


def test_a_refused_earlier_resume_is_retried_with_the_recorded_answer(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        seq = _answered_row(w)
        with w.store.write() as transaction:
            record_resume(
                transaction,
                seq,
                ResumeOutcome.REFUSED,
                detail="lock held",
                log=None,
                at=START,
            )

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert w.spawned.answering == []
        assert len(w.spawned.resumes) == 1
        assert _answers(w)[0].resume_outcome is ResumeOutcome.RESUMED


def test_a_pm_answer_on_a_waiting_question_is_delivered_by_the_next_call(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _claim_row(w, age_seconds=0)
        with w.store.write() as transaction:
            settle_waiting(
                transaction,
                KEY,
                OLD_RUN,
                reason=DeclineReason.CHECK_SAID_NO,
                detail="no",
                evidence=None,
                now=START,
            )
            add_pm_answer(transaction, KEY, "PM says 250.", now=START)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert w.spawned.resumes[0][-1].endswith("Answer: PM says 250.")
        assert _record(w).waiting_reason is DeclineReason.CHECK_SAID_NO


def test_a_question_waiting_on_the_pm_is_skipped_with_its_reason(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _claim_row(w, age_seconds=0)
        with w.store.write() as transaction:
            settle_waiting(
                transaction,
                KEY,
                OLD_RUN,
                reason=DeclineReason.UNCITED,
                detail=None,
                evidence=None,
                now=START,
            )

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.SKIPPED
        assert result.skip_reason is SkipReason.WAITING_ON_PM
        assert result.detail == "uncited"
        assert w.spawned.argvs == []


@pytest.mark.parametrize(
    "outcome", [ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED]
)
def test_an_answer_that_was_handed_over_is_settled(
    tmp_path: Path, outcome: ResumeOutcome
) -> None:
    with world(tmp_path) as w:
        seq = _answered_row(w)
        with w.store.write() as transaction:
            record_resume(transaction, seq, outcome, detail=None, log=None, at=START)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.SKIPPED
        assert result.skip_reason is SkipReason.SETTLED
        assert w.spawned.argvs == []


# 7.11: the dead claim


def test_a_running_answering_run_and_a_young_claim_is_already_claimed(
    tmp_path: Path,
) -> None:
    with world(
        tmp_path, answering_poll=lambda run_id: _ended(RunOutcome.TIMED_OUT, run_id)
    ) as w:
        _claim_row(w, age_seconds=WAIT / 2)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.SKIPPED
        assert result.skip_reason is SkipReason.ALREADY_CLAIMED
        assert _record(w).state is QuestionState.CLAIMED


def test_a_running_answering_run_and_an_old_claim_stalls_and_a_late_reply_is_ignored(
    tmp_path: Path,
) -> None:
    with world(
        tmp_path, answering_poll=lambda run_id: _ended(RunOutcome.TIMED_OUT, run_id)
    ) as w:
        _claim_row(w, age_seconds=WAIT * 2)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.WAITING_ON_PM, result
        assert result.waiting_reason is DeclineReason.ANSWERING_RUN_STALLED
        assert _record(w).state is QuestionState.WAITING_ON_PM
        # The answering run finishes after all: its reply finds the claim gone.
        _write_replies(w, OLD_RUN)
        late = settle(
            w.store,
            w.deps,
            Claim(
                key=KEY,
                answering_run_id=OLD_RUN,
                question=QUESTION,
                passage_ids=frozenset({"P1"}),
                settings=w.member_settings(),
                wait_seconds=WAIT,
            ),
            RunEnded(_ended(RunOutcome.COMPLETED, OLD_RUN)),
        )
        assert late == Superseded()
        assert _answers(w) == ()


def test_a_completed_answering_run_whose_claimant_died_is_settled_then_resumed(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _claim_row(w, age_seconds=WAIT * 2)
        _write_replies(w, OLD_RUN)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert w.spawned.answering == []
        assert _record(w).state is QuestionState.ANSWERED
        rows = _answers(w)
        assert [r.answered_by for r in rows] == [AnsweredBy.ANSWERER]
        assert rows[0].resume_outcome is ResumeOutcome.RESUMED


def _poll_for(kind: str, run_id: str) -> RunPoll:
    if kind == "failed":
        failure = RunFailure(kind="provider_error", message="boom")
        return _ended(RunOutcome.FAILED, run_id, failure=failure.model_dump())
    if kind == "paused":
        return poll_result(PAUSED_INTERACTIVE, run_id)
    return _ended(RunOutcome.ORPHANED, run_id)


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("failed", DeclineReason.ANSWERING_RUN_FAILED),
        ("paused", DeclineReason.ANSWERING_RUN_FAILED),
        ("orphaned", DeclineReason.ANSWERING_RUN_ORPHANED),
    ],
)
def test_a_failed_paused_or_orphaned_answering_run_settles_waiting_with_its_reason(
    tmp_path: Path, kind: str, reason: DeclineReason
) -> None:
    with world(tmp_path, answering_poll=partial(_poll_for, kind)) as w:
        _claim_row(w, age_seconds=0)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.WAITING_ON_PM, result
        assert result.waiting_reason is reason
        assert w.spawned.argvs == []


def test_a_run_that_does_not_exist_yet_and_a_young_claim_is_already_claimed(
    tmp_path: Path,
) -> None:
    with world(
        tmp_path, answering_poll=lambda run_id: _ended(RunOutcome.NOT_FOUND, run_id)
    ) as w:
        _claim_row(w, age_seconds=WAIT / 2)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.SKIPPED
        assert result.skip_reason is SkipReason.ALREADY_CLAIMED
        assert w.spawned.argvs == []


def test_a_run_that_does_not_exist_and_an_old_claim_is_restarted_under_a_new_id(
    tmp_path: Path,
) -> None:
    def not_found_only_for_the_old_run(run_id: str) -> RunPoll:
        outcome = RunOutcome.NOT_FOUND if run_id == OLD_RUN else RunOutcome.COMPLETED
        return _ended(outcome, run_id)

    with world(tmp_path, answering_poll=not_found_only_for_the_old_run) as w:
        _claim_row(w, age_seconds=WAIT * 2)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        record = _record(w)
        assert record.answering_run_id not in (None, OLD_RUN)
        assert result.answering_run_id == record.answering_run_id
        (answering,) = w.spawned.answering
        assert record.answering_run_id in answering
        assert scratch_path(w.deps.answering_dir, str(record.answering_run_id)).is_dir()
        assert record.passages
        assert len(_answers(w)) == 1


def test_a_poll_failure_on_the_answering_run_raises_and_writes_nothing(
    tmp_path: Path,
) -> None:
    with world(
        tmp_path, answering_poll=lambda run_id: PollFailure(f"sq broke on {run_id}")
    ) as w:
        _claim_row(w, age_seconds=WAIT * 2)

        with pytest.raises(SquadronError, match="sq broke"):
            w.handle()

        assert _record(w).state is QuestionState.CLAIMED
        assert _answers(w) == ()


def test_an_unreadable_answering_run_raises_and_writes_nothing(tmp_path: Path) -> None:
    with world(
        tmp_path, answering_poll=lambda run_id: _ended(RunOutcome.UNREADABLE, run_id)
    ) as w:
        _claim_row(w, age_seconds=WAIT * 2)

        with pytest.raises(SquadronError, match="unreadable"):
            w.handle()

        assert _record(w).state is QuestionState.CLAIMED
