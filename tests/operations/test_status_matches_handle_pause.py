"""The D3 cross-check: the same rows and run through ``status`` and ``handle_pause``
(slice 224, 3.8). Every run ``status`` shows as ``unhandled``, ``claim_stale`` or
``answered_unresumed`` is one ``handle_pause`` does not skip; every other class is."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

import pytest
from store.question_support import PASSAGE
from user_configs import user_config

from amoeba.answering.values import AnsweringEvidence, DeclineReason
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.pause_models import HandlePauseOutcome, SkipReason
from amoeba.operations.status import status
from amoeba.operations.status_runs import HANDLED_BY_HANDLE_PAUSE
from amoeba.store.answers import Settled, answers_of, record_resume, settle_answered
from amoeba.store.questions import (
    NewQuestion,
    close_question,
    get_question,
    insert_question,
)
from amoeba.store.vocabulary import ClosedReason, ResumeOutcome
from amoeba.upstream.squadron.run_list import ListedCheckpoint, ListedRun
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument
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
from operations.pause_support import START

OLD_RUN = "amoeba-20261110T110000Z-oldoldoldold"
WAIT = 600.0


def _claim(w: World, *, age_seconds: float) -> None:
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


def _answered(w: World) -> int:
    _claim(w, age_seconds=0)
    settled = settle_answered(
        w.store,
        KEY,
        OLD_RUN,
        answer=ANSWER_TEXT,
        cited=("P1",),
        evidence=AnsweringEvidence(),
        gate=lambda _prior: None,
        now=START,
    )
    assert isinstance(settled, Settled)
    return settled.answer_seq


def _no_row(w: World) -> None:
    del w


def _prompt_only(w: World) -> None:
    path = w.runs_dir / f"{RUN}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["execution_mode"] = "prompt-only"
    path.write_text(json.dumps(document), encoding="utf-8")


def _live_claim(w: World) -> None:
    _claim(w, age_seconds=WAIT / 2)


def _stale_claim(w: World) -> None:
    _claim(w, age_seconds=WAIT + 1)


def _waiting(w: World) -> None:
    new = NewQuestion(
        key=KEY,
        member_id=PROJECT_ID,
        question=QUESTION,
        checkout=str(w.directory),
        slice_label=None,
        source_commit=None,
        passages=None,
        answering_run_id=None,
        waiting_reason=DeclineReason.ANSWER_LIMIT_REACHED,
        waiting_detail=None,
    )
    with w.store.write() as transaction:
        insert_question(transaction, new, now=START)


def _unresumed(w: World) -> None:
    _answered(w)


def _settled(w: World) -> None:
    seq = _answered(w)
    with w.store.write() as transaction:
        record_resume(
            transaction, seq, ResumeOutcome.RESUMED, detail=None, log=None, at=START
        )


def _closed(w: World) -> None:
    _waiting(w)
    with w.store.write() as transaction:
        row = get_question(transaction, KEY)
        assert row is not None
        assert close_question(
            transaction,
            KEY,
            ClosedReason.RUN_MOVED_ON,
            "completed",
            row.state,
            row.updated_at,
            START,
        )


@dataclass(frozen=True)
class Scenario:
    setup: Callable[[World], None]
    status_class: PauseClass
    #: The skip the call must give; ``None`` when it must not be skipped.
    skip: SkipReason | None


SCENARIOS = {
    "no_row_sdk": Scenario(_no_row, PauseClass.UNHANDLED, None),
    "no_row_prompt_only": Scenario(
        _prompt_only, PauseClass.PROMPT_ONLY, SkipReason.PROMPT_ONLY
    ),
    "live_claim": Scenario(
        _live_claim, PauseClass.CLAIM_LIVE, SkipReason.ALREADY_CLAIMED
    ),
    "stale_claim": Scenario(_stale_claim, PauseClass.CLAIM_STALE, None),
    "waiting": Scenario(_waiting, PauseClass.WAITING_ON_PM, SkipReason.WAITING_ON_PM),
    "answered_unresumed": Scenario(_unresumed, PauseClass.ANSWERED_UNRESUMED, None),
    "settled": Scenario(_settled, PauseClass.SETTLED, SkipReason.SETTLED),
    "closed": Scenario(_closed, PauseClass.CLOSED, SkipReason.CLOSED),
}


def _answering_run_is_still_going(run_id: str) -> RunOutcomeDocument:
    return RunOutcomeDocument(run_id=run_id, outcome=RunOutcome.TIMED_OUT)


def _listed(w: World) -> ListedRun:
    checkpoint = PAUSE.checkpoint
    assert checkpoint is not None
    return ListedRun(
        run_id=RUN,
        pipeline="asks_question",
        status="paused",
        working_directory=w.directory,
        checkpoint=ListedCheckpoint(
            kind=checkpoint.kind,
            paused_at=checkpoint.paused_at_text,
            question=checkpoint.question,
        ),
    )


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_status_and_handle_pause_agree_on_every_class(
    tmp_path: Path, name: str
) -> None:
    scenario = SCENARIOS[name]
    with world(tmp_path, answering_poll=_answering_run_is_still_going) as w:
        scenario.setup(w)
        deps = replace(
            w.deps,
            list_runs=lambda: [_listed(w)],
            project_names=lambda: {PROJECT_ID: "the-member"},
        )

        shown = status(w.store, user_config(), {}, directory=w.directory, deps=deps)
        handled = w.handle()

    (program,) = shown.programs
    (member,) = program.members
    (entry,) = member.runs
    assert entry.pause is scenario.status_class
    if scenario.status_class in HANDLED_BY_HANDLE_PAUSE:
        assert handled.outcome is not HandlePauseOutcome.SKIPPED, handled
        assert entry.next is not None
    else:
        assert handled.outcome is HandlePauseOutcome.SKIPPED, handled
        assert handled.skip_reason is scenario.skip


def test_a_closed_pause_shows_why_and_has_no_next_and_writes_nothing(
    tmp_path: Path,
) -> None:
    with world(tmp_path, answering_poll=_answering_run_is_still_going) as w:
        _closed(w)
        deps = replace(
            w.deps,
            list_runs=lambda: [_listed(w)],
            project_names=lambda: {PROJECT_ID: "the-member"},
        )

        shown = status(w.store, user_config(), {}, directory=w.directory, deps=deps)
        handled = w.handle()
        with w.store.read() as transaction:
            answers = answers_of(transaction, KEY)

    (entry,) = shown.programs[0].members[0].runs
    assert entry.pause is PauseClass.CLOSED
    assert entry.next is None
    assert entry.detail is not None
    assert "run_moved_on: completed" in entry.detail
    assert "still paused in Squadron" in entry.detail
    assert "sq run --resume" in entry.detail
    assert handled.skip_reason is SkipReason.CLOSED
    assert answers == ()
