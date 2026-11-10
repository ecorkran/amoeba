"""The pause command is not started for a run started with ``--no-pause-hook``
(slice 223, task 9.2a).

A member's ``.squadron.toml`` sets ``pipeline.on_pause_command`` to a script that
writes a marker named by the run id Squadron appends. The same pause pipeline is
started twice: with the answering run's opt-out flag (no marker) and without it (the
control: a marker). Squadron has no step that ends paused without a model call, so each
run makes one cheap model call; the hook is what is under test.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from live_settings import LiveSettings

from amoeba.upstream.squadron.launch import mint_run_id
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument
from live.pause.harness import PauseWorld, start_pause

MARKER_WAIT_SECONDS = 60
POLL_SECONDS = 0.5
HOOK_KEY = "pipeline.on_pause_command"
HOOK_SCRIPT = (
    "import pathlib, sys\n"
    "directory = pathlib.Path(sys.argv[1])\n"
    "directory.mkdir(parents=True, exist_ok=True)\n"
    "(directory / sys.argv[2]).write_text('fired')\n"
)


def _configure_hook(world: PauseWorld, markers: Path) -> None:
    script = markers.parent / "hook.py"
    script.write_text(HOOK_SCRIPT, encoding="utf-8")
    command = f"{sys.executable} {script} {markers}"
    # A JSON string is a valid TOML basic string.
    (world.repo / ".squadron.toml").write_text(
        f'"{HOOK_KEY}" = {json.dumps(command)}\n', encoding="utf-8"
    )


def _paused(run_id: str, world: PauseWorld, *, opt_out: bool) -> None:
    started = start_pause(world, run_id, opt_out=opt_out)
    assert isinstance(started.poll, RunOutcomeDocument), started.sq_output
    assert started.poll.outcome is RunOutcome.PAUSED, started.sq_output


def test_the_opt_out_leaves_no_marker_and_the_control_leaves_one(
    pause_world: PauseWorld, tmp_path: Path, live_settings: LiveSettings
) -> None:
    del live_settings
    markers = tmp_path / "markers"
    _configure_hook(pause_world, markers)
    with_flag = mint_run_id(datetime.now(UTC))
    _paused(with_flag, pause_world, opt_out=True)
    control = mint_run_id(datetime.now(UTC))
    _paused(control, pause_world, opt_out=False)

    deadline = time.monotonic() + MARKER_WAIT_SECONDS
    while not (markers / control).exists():
        assert time.monotonic() < deadline, "the control's hook never fired"
        time.sleep(POLL_SECONDS)

    assert (markers / control).read_text(encoding="utf-8") == "fired"
    assert not (markers / with_flag).exists(), "the opt-out run started the hook"
