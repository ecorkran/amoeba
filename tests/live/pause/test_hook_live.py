"""The pause hook runs ``amoeba handle-pause`` on a real pause (slice 229, D14).

The member's ``.squadron.toml`` sets ``pipeline.on_pause_command`` to the absolute
``amoeba`` path and ``handle-pause`` (Squadron appends the run id), and the run is
started without the opt-out flag. The test waits for the hook to run, then checks what
it left: a calls-log line for the run in the test's ``AMOEBA_HOME``, the recorded
question, and ``list`` showing it. A wrong result fails the test; nothing is retried.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from live_settings import LiveSettings

from amoeba.config.home import calls_log_dir
from amoeba.operations.names import OperationName
from amoeba.upstream.squadron.launch import mint_run_id
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument
from live.pause.harness import (
    AMOEBA,
    PauseWorld,
    result_of,
    run_amoeba,
    start_pause,
    store_rows,
)

HOOK_KEY = "pipeline.on_pause_command"
CALL_WAIT_SECONDS = 900
POLL_SECONDS = 1.0


def _calls_for(run_id: str) -> list[dict[str, Any]]:
    """The calls-log lines of ``run_id`` (the test's ``AMOEBA_HOME`` is the world's)."""
    return [
        entry
        for day in sorted(calls_log_dir().glob("*.jsonl"))
        for entry in map(json.loads, day.read_text(encoding="utf-8").splitlines())
        if entry["run_id"] == run_id
    ]


def test_the_hook_handles_a_real_pause_and_list_shows_it(
    pause_world: PauseWorld, live_settings: LiveSettings
) -> None:
    del live_settings
    command = f"{AMOEBA} {OperationName.HANDLE_PAUSE.cli_name}"
    # A JSON string is a valid TOML basic string.
    (pause_world.repo / ".squadron.toml").write_text(
        f'"{HOOK_KEY}" = {json.dumps(command)}\n', encoding="utf-8"
    )
    run_id = mint_run_id(datetime.now(UTC))

    started = start_pause(pause_world, run_id, opt_out=False)
    assert isinstance(started.poll, RunOutcomeDocument), started.sq_output
    assert started.poll.outcome is RunOutcome.PAUSED, started.sq_output

    deadline = time.monotonic() + CALL_WAIT_SECONDS
    while not _calls_for(run_id):
        assert time.monotonic() < deadline, "the hook never ran handle-pause"
        time.sleep(POLL_SECONDS)

    (call,) = _calls_for(run_id)
    assert call["outcome"] == "resumed", call
    ((state, question),) = store_rows(
        pause_world, "SELECT state, question FROM questions WHERE run_id = ?", (run_id,)
    )
    assert state == "answered"
    shown = result_of(run_amoeba(pause_world, "list", "--all"))
    entries: list[dict[str, Any]] = shown["settled"]  # type: ignore[assignment]
    (settled,) = [item for item in entries if item["run_id"] == run_id]
    assert settled["question"] == question
    assert settled["ended"] == "answerer"
