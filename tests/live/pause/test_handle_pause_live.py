"""``amoeba handle_pause`` on a real pause with real models (slice 223, task 9.2).

A throwaway member's run stops on a question its rules settle; ``handle_pause`` is
called from the member's checkout, answers it and resumes the run. A wrong outcome
fails the test; nothing is retried.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from live_harness import POLL_INTERVAL_SECONDS
from live_settings import LiveSettings

from amoeba.upstream.squadron.launch import mint_run_id
from amoeba.upstream.squadron.run_outcome import (
    PollFailure,
    RunOutcome,
    RunOutcomeDocument,
    poll_run,
)
from live.pause.harness import (
    PauseWorld,
    result_of,
    run_amoeba,
    start_pause,
    store_rows,
)

LEAVE_PAUSE_SECONDS = 180
POLL_CALL_TIMEOUT_SECONDS = 30.0


def _wait_until_not_running(run_id: str) -> RunOutcomeDocument:
    """Poll until the run is no longer running (the resumed child has finished)."""
    deadline = time.monotonic() + LEAVE_PAUSE_SECONDS
    while time.monotonic() < deadline:
        poll = poll_run(run_id, timeout_seconds=POLL_CALL_TIMEOUT_SECONDS)
        assert not isinstance(poll, PollFailure), poll
        if poll.outcome is not RunOutcome.TIMED_OUT:
            return poll
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(f"run {run_id} was still running after {LEAVE_PAUSE_SECONDS}s")


def test_a_real_pause_is_answered_and_the_run_leaves_it(
    pause_world: PauseWorld, live_settings: LiveSettings
) -> None:
    del live_settings
    run_id = mint_run_id(datetime.now(UTC))
    started = start_pause(pause_world, run_id, opt_out=True)
    assert isinstance(started.poll, RunOutcomeDocument), started.sq_output
    assert started.poll.outcome is RunOutcome.PAUSED, started.sq_output
    checkpoint = started.poll.checkpoint
    assert checkpoint is not None and checkpoint.paused_at_text is not None
    original_pause = checkpoint.paused_at_text

    completed = run_amoeba(pause_world, "handle_pause", run_id)

    assert completed.returncode == 0, completed.stderr
    result = result_of(completed)
    assert result["outcome"] == "resumed", result
    assert result["key"] == {"run_id": run_id, "paused_at": original_pause}
    (question,) = store_rows(
        pause_world,
        "SELECT state, question, slice_label, passages, evidence FROM questions",
    )
    state, text, slice_label, passages, evidence = question
    assert state == "answered"
    assert text == checkpoint.question
    assert slice_label == "none"
    assert json.loads(str(passages)), "the record keeps the passages it was given"
    assert json.loads(str(evidence))["verdict"] == "yes"
    ((answered_by, answer, cited, resume_outcome, resume_log),) = store_rows(
        pause_world,
        "SELECT answered_by, answer, cited, resume_outcome, resume_log FROM answers",
    )
    assert answered_by == "answerer"
    assert str(answer).strip()
    assert json.loads(str(cited))
    assert resume_outcome == "resumed"
    assert resume_log

    after = _wait_until_not_running(run_id)
    left_the_pause = (
        after.outcome is not RunOutcome.PAUSED
        or after.checkpoint is None
        or after.checkpoint.paused_at_text != original_pause
    )
    assert left_the_pause, after
