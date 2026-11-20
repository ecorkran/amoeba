"""A standing answer settles a real pause, and withdrawn it does not (slice 230, 9.1).

A throwaway member whose rules say nothing about fixture versions is asked "Should I
bump the fixture version?". With the walkthrough's standing answer (reach ``all``)
given, ``handle-pause`` answers it citing that standing answer and resumes the run;
after ``withdraw``, the same question waits on the PM. Real ``sq``, ``cf`` and
models; a wrong outcome fails the test and nothing is retried.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast

from live_settings import LiveSettings

from amoeba.upstream.squadron.launch import mint_run_id
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument
from live.pause.harness import (
    PauseWorld,
    inert_hook,
    result_of,
    run_amoeba,
    start_pause,
)

PIPELINE: Final = Path(__file__).parent / "asks_fixture_version.yaml"
RULING: Final = (
    "When an agent asks whether to bump the fixture version, the answer is no: "
    "fixture versions are never bumped."
)


def _amoeba(world: PauseWorld, *arguments: str) -> dict[str, object]:
    completed = run_amoeba(world, *arguments)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    return result_of(completed)


def _paused_run(world: PauseWorld) -> str:
    run_id = mint_run_id(datetime.now(UTC))
    started = start_pause(world, run_id, opt_out=True, pipeline=PIPELINE)
    assert isinstance(started.poll, RunOutcomeDocument), started.sq_output
    assert started.poll.outcome is RunOutcome.PAUSED, started.sq_output
    return run_id


def _cited(world: PauseWorld, run_id: str) -> list[dict[str, object]]:
    """The passages the automatic answer to ``run_id`` cited, from ``decisions``."""
    listed = _amoeba(world, "decisions", "--since", "2026-01-01T00:00:00+00:00")
    records = cast("list[dict[str, Any]]", listed["records"])
    (record,) = [r for r in records if r["run_id"] == run_id]
    return cast("list[dict[str, object]]", record["based_on"]["cited"])


def test_a_standing_answer_settles_the_question_and_withdrawn_it_waits(
    pause_world: PauseWorld, live_settings: LiveSettings
) -> None:
    del live_settings
    world = inert_hook(pause_world)
    given = _amoeba(world, "standing", "--text", RULING)
    assert given["outcome"] == "given", given
    standing_id = given["standing_id"]

    answered_run = _paused_run(world)
    answered = _amoeba(world, "handle-pause", answered_run)

    assert answered["outcome"] == "resumed", answered
    standing_citations = [
        c for c in _cited(world, answered_run) if c["kind"] == "standing_answer"
    ]
    assert [c["source"] for c in standing_citations] == [f"standing:{standing_id}"]

    withdrawn = _amoeba(world, "withdraw", str(standing_id), "--reason", "walkthrough")
    assert withdrawn["outcome"] == "withdrawn", withdrawn
    waiting_run = _paused_run(world)
    waiting = _amoeba(world, "handle-pause", waiting_run)

    assert waiting["outcome"] == "waiting_on_pm", waiting
