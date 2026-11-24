"""The pause path on steps: what each path does with the hub's answer (slice 262, 4.8).

The existing pause, hold and settle tests run on ``LocalSteps`` unchanged; these are
the cases the move itself adds.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fake_sq import COMPLETED, poll_result
from store.question_support import PASSAGE

from amoeba.answering.values import AnsweringEvidence
from amoeba.operations.pause_claim import restart_dead_claim
from amoeba.operations.pause_models import HandlePauseOutcome, SkipReason
from amoeba.operations.steps.limits import pause_claim_seconds
from amoeba.operations.steps.resume import ResumeClaimed, claim_resume
from amoeba.store.answers import Settled, settle_answered
from amoeba.store.models import QuestionRecord
from amoeba.store.questions import NewQuestion, get_question, insert_question
from amoeba.store.vocabulary import QuestionState
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_outcome import PollFailure
from operations.handle_rig import (
    ANSWER_TEXT,
    KEY,
    PAUSE,
    PROJECT_ID,
    QUESTION,
    RUN,
    World,
    world,
)
from operations.held_support import begin_for, steps_for, target_of
from operations.pause_support import START
from operations.ways import WAYS

OLD_RUN = "amoeba-20261110T110000Z-oldoldoldold"


def _claim_row(w: World, *, age: timedelta) -> None:
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
        insert_question(transaction, new, now=START - age)


def _record(w: World) -> QuestionRecord:
    with w.store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    return record


@pytest.mark.parametrize("way", WAYS)
def test_a_run_that_is_not_paused_makes_no_context_forge_call(
    tmp_path: Path, way: str
) -> None:
    done = poll_result(COMPLETED, RUN)
    with world(tmp_path, way=way, paused_polls=(done,)) as w:
        calls: list[Sequence[str]] = []
        real = w.deps.cf_run

        def counting(
            argv: Sequence[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            return real(argv, **kwargs)

        w.deps = replace(w.deps, cf_run=counting)

        result = w.handle()

        assert result.skip_reason is SkipReason.NOT_PAUSED
        assert [argv for argv in calls if argv[0] == "cf"] == []


def test_two_calls_that_read_one_stale_claim_replace_it_once(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _claim_row(w, age=timedelta(seconds=pause_claim_seconds(w.config)))
        # Both calls read the claim as stale before either replaces it.
        begun = begin_for(w)
        assert begun.claim_stale
        target = target_of(w)

        first = restart_dead_claim(steps_for(w), w.deps, target, begun, OLD_RUN)
        second = restart_dead_claim(steps_for(w), w.deps, target, begun, OLD_RUN)

        assert first.outcome is HandlePauseOutcome.RESUMED, first
        assert second.outcome is HandlePauseOutcome.SKIPPED
        assert second.skip_reason is SkipReason.ALREADY_CLAIMED
        assert len(w.spawned.answering) == 1


def test_a_question_on_another_machine_is_skipped_and_nothing_starts(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _claim_row(w, age=timedelta(0))
        with w.store.write() as transaction:
            transaction.execute(
                "INSERT INTO machines (name, owner_id, created_at) "
                "VALUES ('beta', (SELECT owner_id FROM owners), 't')"
            )
            transaction.execute(
                "UPDATE questions SET machine_id = "
                "(SELECT machine_id FROM machines WHERE name = 'beta')"
            )

        result = w.handle()

        assert result.skip_reason is SkipReason.OTHER_MACHINE
        assert "beta" in (result.detail or "")
        assert _record(w).state is QuestionState.CLAIMED
        assert w.spawned.argvs == []


def test_a_resume_claim_in_flight_is_skipped_and_starts_nothing(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _claim_row(w, age=timedelta(0))
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
        with w.store.write() as transaction:
            held = claim_resume(transaction, outcome.answer_seq, START, 216.5)
        assert isinstance(held, ResumeClaimed)

        result = w.handle()

        assert result.skip_reason is SkipReason.RESUME_IN_PROGRESS
        assert w.spawned.argvs == []


def test_an_answered_question_whose_first_resume_poll_is_unreadable_raises(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=(PAUSE, PollFailure("sq broke"))) as w:
        _claim_row(w, age=timedelta(0))
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

        with pytest.raises(SquadronError, match="sq broke"):
            w.handle()

        assert w.spawned.argvs == []


def test_a_hook_or_hand_run_handle_pause_is_not_counted_as_an_automatic_start(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _claim_row(w, age=timedelta(seconds=pause_claim_seconds(w.config)))

        w.handle()

        with w.store.read() as transaction:
            rows = transaction.execute(
                "SELECT start_count, start_attempted_at FROM questions"
            ).fetchall()
        assert [tuple(row) for row in rows] == [(0, None)]
