"""The slice 224 verification walkthrough, step by step, with real ``sq``, ``cf`` and
models (slice 224, task 5.3).

A throwaway member (its own Context Forge data directory and ``AMOEBA_HOME``) runs
real pipelines that pause on a question. ``amoeba status``, ``handle_pause``,
``decisions``, ``mark_read`` and ``answer`` are the real commands. A wrong result fails
the test; nothing is retried.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from live_harness import PipelineRun
from live_settings import LiveSettings

from amoeba.upstream.squadron.launch import mint_run_id
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument
from live.pause.harness import PauseWorld, result_of, run_amoeba, start_pause

UNSETTLED_PIPELINE = Path(__file__).parent / "asks_unsettled_question.yaml"


def _amoeba(
    world: PauseWorld, *arguments: str, cwd: Path | None = None, expect: int = 0
) -> dict[str, Any]:
    completed = run_amoeba(world, *arguments, cwd=cwd)
    assert completed.returncode == expect, (
        f"amoeba {' '.join(arguments)} exited {completed.returncode}\n"
        f"{completed.stdout}\n{completed.stderr}"
    )
    return dict(result_of(completed))


def _paused(started: PipelineRun) -> str:
    assert isinstance(started.poll, RunOutcomeDocument), started.sq_output
    assert started.poll.outcome is RunOutcome.PAUSED, started.sq_output
    assert started.poll.checkpoint is not None
    assert started.poll.checkpoint.paused_at_text is not None
    return started.poll.checkpoint.paused_at_text


def _member(status: dict[str, Any]) -> dict[str, Any]:
    (program,) = status["programs"]
    (member,) = program["members"]
    member_entry: dict[str, Any] = member
    return member_entry


def _run_entry(status: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    for entry in _member(status)["runs"]:
        if entry["run_id"] == run_id:
            run_entry: dict[str, Any] = entry
            return run_entry
    return None


def test_the_walkthrough(
    pause_world: PauseWorld, live_settings: LiveSettings, tmp_path: Path
) -> None:
    del live_settings
    world = pause_world

    # Step 2: a missed hook. With no hook the run pauses and nothing records it.
    settled_run = mint_run_id(datetime.now(UTC))
    original_pause = _paused(start_pause(world, settled_run, opt_out=True))
    before = _amoeba(world, "status")
    assert before["outcome"] == "listed"
    entry = _run_entry(before, settled_run)
    assert entry is not None, before
    assert entry["pause"] == "unhandled", entry
    assert entry["next"]["operation"] == "handle_pause"
    assert entry["next"]["run_id"] == settled_run
    assert Path(entry["next"]["directory"]).resolve() == world.repo.resolve()
    assert entry["next"]["paused_at"] == original_pause

    # Step 3: catch up from that directory.
    handled = _amoeba(world, "handle_pause", settled_run)
    assert handled["outcome"] == "resumed", handled
    after = _amoeba(world, "status")
    caught_up = _run_entry(after, settled_run)
    # The pipeline ends every step on a question, so once resumed the run may pause
    # again with a new question: a new pause, which has its own missed hook. The
    # original pause is what must no longer be unhandled.
    assert (
        caught_up is None
        or caught_up["pause"] != "unhandled"
        or caught_up["checkpoint"]["paused_at"] != original_pause
    ), caught_up

    # Step 4: decisions.
    listed = _amoeba(world, "decisions")
    (record,) = listed["records"]
    assert record["answered_by"] == "answerer"
    assert record["run_id"] == settled_run
    assert record["based_on"]["cited"], record
    assert record["based_on"]["check_verdict"] == "yes"
    assert record["resume"]["outcome"] == "resumed"
    read_through = listed["read_through"]
    assert isinstance(read_through, int)

    # Step 5: mark read.
    moved = _amoeba(world, "mark_read", "--through", str(read_through))
    assert moved["outcome"] == "moved", moved
    empty = _amoeba(world, "decisions")
    assert empty["records"] == []
    assert empty["read_through"] is None
    beyond = _amoeba(world, "mark_read", "--through", "999999", expect=1)
    assert beyond["rejection"] == "beyond_last_record"

    # Step 6: a pause the rules do not settle waits on the PM.
    waiting_run = mint_run_id(datetime.now(UTC))
    waiting_pause = _paused(
        start_pause(world, waiting_run, opt_out=True, pipeline=UNSETTLED_PIPELINE)
    )
    declined = _amoeba(world, "handle_pause", waiting_run)
    assert declined["outcome"] == "waiting_on_pm", declined
    reason = declined["waiting_reason"]
    shown = _amoeba(world, "status")
    waiting = [
        item
        for item in _member(shown)["waiting_on_pm"]
        if item["run_id"] == waiting_run
    ]
    assert len(waiting) == 1, shown
    assert waiting[0]["waiting_reason"] == reason
    assert waiting[0]["run_state"] == "at_pause"
    assert waiting[0]["next"] == {
        "operation": "answer",
        "run_id": waiting_run,
        "paused_at": waiting_pause,
        "directory": None,
    }
    answered = _amoeba(world, "answer", waiting_run, "--text", "Use teal.")
    assert answered["outcome"] == "recorded", answered
    final = _amoeba(world, "decisions")
    (pm_record,) = final["records"]
    assert pm_record["answered_by"] == "pm"
    assert pm_record["based_on"]["waiting_reason"] == reason

    # Step 7: scope. From a directory in no program every program is listed.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    everywhere = _amoeba(world, "status", cwd=elsewhere)
    assert [program["program"] for program in everywhere["programs"]] == ["live-pause"]
    unknown = _amoeba(world, "status", "--program", "nope", cwd=elsewhere, expect=1)
    assert unknown["rejection"] == "unknown_program"
    assert "live-pause" in unknown["problems"][0]
