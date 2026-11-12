"""``handle_pause`` closes this run's older open questions (slice 228, D4, 7.5)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run
from store.question_support import NOW, waiting_question

from amoeba.operations.pause_models import HandlePauseOutcome, SkipReason
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_outcome import PollFailure
from operations.handle_rig import KEY, PROJECT_ID, RUN, World, world

EARLIER = QuestionKey(RUN, "2026-11-09T08:00:00+00:00")


def _waiting_at(w: World, key: QuestionKey) -> None:
    with w.store.write() as transaction:
        insert_question(
            transaction, waiting_question(key, member_id=PROJECT_ID), now=NOW
        )


def _row(store: Store, key: QuestionKey) -> QuestionRecord | None:
    with store.read() as transaction:
        return get_question(transaction, key)


def _closed_as_moved_on(w: World) -> None:
    row = _row(w.store, EARLIER)
    assert row is not None
    assert row.state is QuestionState.CLOSED
    assert row.closed_reason is ClosedReason.RUN_MOVED_ON
    assert row.closed_detail == f"paused at {KEY.paused_at}"


def test_the_hook_at_a_later_pause_closes_the_earlier_row_and_handles_the_new_one(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _waiting_at(w, EARLIER)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert result.key == KEY
        _closed_as_moved_on(w)
        assert result.detail is not None
        assert "closed the question at" in result.detail
        assert "run_moved_on" in result.detail
        current = _row(w.store, KEY)
        assert current is not None
        assert current.state is QuestionState.ANSWERED


def test_a_prompt_only_skip_still_sweeps(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _waiting_at(w, EARLIER)
        path = w.runs_dir / f"{RUN}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["execution_mode"] = "prompt-only"
        path.write_text(json.dumps(document), encoding="utf-8")

        result = w.handle()

        assert result.skip_reason is SkipReason.PROMPT_ONLY
        _closed_as_moved_on(w)
        assert result.detail is not None and "closed the question" in result.detail


def test_a_not_a_project_skip_still_sweeps(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _waiting_at(w, EARLIER)
        w.deps = replace(w.deps, cf_run=fake_cf_run(OUTSIDE_ANY_PROJECT))

        result = w.handle()

        assert result.skip_reason is SkipReason.NOT_A_PROJECT
        _closed_as_moved_on(w)


def test_an_answering_runs_id_has_no_rows_and_sweeps_nothing(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _waiting_at(w, EARLIER)  # a different run's row: must stay open
        other = QuestionKey("another-run", EARLIER.paused_at)
        with w.store.write() as transaction:
            insert_question(
                transaction, waiting_question(other, member_id=PROJECT_ID), now=NOW
            )

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED
        untouched = _row(w.store, other)
        assert untouched is not None
        assert untouched.state is QuestionState.WAITING_ON_PM


def test_a_poll_failure_raises_as_before_and_closes_nothing(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=(PollFailure("sq runs wait timed out"),)) as w:
        _waiting_at(w, EARLIER)

        with pytest.raises(SquadronError, match="timed out"):
            w.handle()

        row = _row(w.store, EARLIER)
        assert row is not None
        assert row.state is QuestionState.WAITING_ON_PM


def test_a_call_with_nothing_to_sweep_adds_nothing_to_the_detail(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED
        assert result.detail is None
