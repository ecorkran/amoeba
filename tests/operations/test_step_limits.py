"""The two claim limits and where a claim turns stale (slice 262, D5, D6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from user_configs import user_config

from amoeba.config.starter import starter_values
from amoeba.operations.pause_class import ObservedPause, PauseClass, classify_pause
from amoeba.operations.pause_observed import claim_is_stale
from amoeba.operations.resume_timing import resume_bound_seconds
from amoeba.operations.runs_document import RunFileFacts
from amoeba.operations.status_placement import PlacedRun
from amoeba.operations.status_runs import classify_runs
from amoeba.operations.steps.limits import (
    CLAIM_CALL_BOUNDS,
    pause_claim_seconds,
    resume_claim_seconds,
)
from amoeba.store.models import Member, MemberSettings, QuestionKey
from amoeba.store.store import BUSY_TIMEOUT_SECONDS
from amoeba.store.vocabulary import QuestionState, RulesFrom
from amoeba.upstream.squadron.run_file import ExecutionMode, RunFacts
from amoeba.wire.times import CALL_BOUND_SECONDS
from operations.runs_doc_support import open_run, project
from operations.status_support import (
    RUN_NOW,
    in_directory,
    question_row,
    recorded_run,
)

CONFIG = user_config()
KEY = QuestionKey("run-1", "2026-11-11T11:00:00+00:00")
ASKING = ObservedPause(
    paused=True, kind="agent_question", paused_at=KEY.paused_at, question="Which?"
)
SDK = RunFacts(params={}, execution_mode=ExecutionMode.SDK, working_directory=None)


def test_the_starter_config_gives_the_designed_limits() -> None:
    starter = starter_values()

    assert starter["answering_wait_seconds"] == CONFIG.answering_wait_seconds
    assert starter["resume_wait_seconds"] == CONFIG.resume_wait_seconds
    assert CLAIM_CALL_BOUNDS * CALL_BOUND_SECONDS == 86
    assert resume_claim_seconds(CONFIG) == 216.5
    assert pause_claim_seconds(CONFIG) == CONFIG.answering_wait_seconds + 86


def test_the_resume_claim_swaps_the_store_wait_for_two_call_bounds() -> None:
    assert resume_claim_seconds(CONFIG) == (
        resume_bound_seconds(CONFIG)
        - BUSY_TIMEOUT_SECONDS
        + CLAIM_CALL_BOUNDS * CALL_BOUND_SECONDS
    )


@pytest.mark.parametrize(
    ("age_offset", "expected"),
    [(-1, PauseClass.CLAIM_LIVE), (0, PauseClass.CLAIM_STALE)],
)
def test_classify_pause_turns_stale_at_the_pause_claim_limit(
    age_offset: float, expected: PauseClass
) -> None:
    limit = pause_claim_seconds(CONFIG)
    row = question_row(KEY, QuestionState.CLAIMED, age_seconds=limit + age_offset)

    stale = claim_is_stale(row, RUN_NOW, limit)
    assert classify_pause(ASKING, row, None, SDK, stale) is expected


MEMBER = Member(
    "demo",
    MemberSettings("member-a", (), (), (), RulesFrom.NAMED),
    RUN_NOW,
    RUN_NOW,
    None,
    "member-a",
    None,
)
PAUSED_RUN = "demo-pause-1"


@pytest.mark.parametrize(
    ("age_offset", "expected"),
    [(-1, PauseClass.CLAIM_LIVE), (0, PauseClass.CLAIM_STALE)],
)
def test_classify_runs_turns_stale_at_the_pause_claim_limit(
    tmp_path: Path, age_offset: float, expected: PauseClass
) -> None:
    run = in_directory(recorded_run(PAUSED_RUN), tmp_path)
    assert run.checkpoint is not None
    assert run.checkpoint.paused_at is not None
    key = QuestionKey(run.run_id, run.checkpoint.paused_at)
    limit = pause_claim_seconds(CONFIG)
    row = question_row(key, QuestionState.CLAIMED, age_seconds=limit + age_offset)
    facts = RunFileFacts(params={}, execution_mode="sdk", working_directory=None)
    placed = (PlacedRun(open_run(run, project("cf-a"), run_file=facts), MEMBER),)

    (item,) = classify_runs(placed, {PAUSED_RUN: (row, None)}, {}, limit, RUN_NOW)

    assert item.entry.pause is expected
