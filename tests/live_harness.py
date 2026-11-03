"""Run the real answering pipeline for the live tier (slice 140, D10).

``sq run`` is launched the way the Runner launches it (detached stdin, working
directory the scratch directory) and watched with the existing ``poll_run``.
The live tests spend real money; this helper adds nothing but a bounded wait.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from process_containment import contained_popen

from amoeba.process import (
    SQ_EXECUTABLE,
    PollFailure,
    RunOutcome,
    RunPoll,
    poll_run,
)
from amoeba.runner.answering.pipeline_file import (
    CHECK_MODEL_PARAM,
    answering_pipeline_path,
)
from amoeba.runner.cf_call import OUTPUT_HEAD_CHARS
from amoeba.runner.launch import mint_run_id

POLL_INTERVAL_SECONDS: Final = 2.0
POLL_CALL_TIMEOUT_SECONDS: Final = 30.0
#: Outcomes that mean "keep waiting" while the launch process is alive.
_NOT_YET: Final = frozenset({RunOutcome.TIMED_OUT, RunOutcome.NOT_FOUND})


@dataclass(frozen=True)
class PipelineRun:
    """A live run: its id, its outcome and the head of ``sq``'s output."""

    run_id: str
    poll: RunPoll
    sq_output: str


def launch_argv(run_id: str, answer_model: str, check_model: str) -> list[str]:
    """The slice design's launch contract; answer-model is the positional target."""
    return [
        SQ_EXECUTABLE,
        "run",
        str(answering_pipeline_path()),
        answer_model,
        "--run-id",
        run_id,
        "-p",
        f"{CHECK_MODEL_PARAM}={check_model}",
    ]


def run_pipeline(
    directory: Path,
    answer_model: str,
    check_model: str,
    timeout_seconds: float,
    environ: Mapping[str, str] | None = None,
) -> PipelineRun:
    """Launch the pipeline in ``directory`` and wait at most ``timeout_seconds``.

    ``environ`` replaces the launch process's environment when given. On the
    deadline the launch process's whole session is killed, so no child keeps
    spending, and the poll is a :class:`PollFailure`; the caller's assertion
    fails with it.
    """
    run_id = mint_run_id(datetime.now(UTC))
    argv = launch_argv(run_id, answer_model, check_model)
    with tempfile.TemporaryFile("w+") as log:
        process = contained_popen(  # noqa: S603 - argv built here, no shell
            argv,
            cwd=directory,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            env=None if environ is None else dict(environ),
            start_new_session=True,
        )
        deadline = time.monotonic() + timeout_seconds
        poll: RunPoll = PollFailure(f"run {run_id} not polled")
        try:
            while time.monotonic() < deadline:
                poll = poll_run(run_id, timeout_seconds=POLL_CALL_TIMEOUT_SECONDS)
                if isinstance(poll, PollFailure):
                    break
                exit_code = process.poll()
                if poll.outcome not in _NOT_YET:
                    break
                if exit_code is not None:
                    poll = PollFailure(
                        f"sq (argv {argv!r}) exited {exit_code} before run "
                        f"{run_id} was found"
                    )
                    break
                time.sleep(POLL_INTERVAL_SECONDS)
            else:
                poll = PollFailure(f"run {run_id} did not finish in {timeout_seconds}s")
        finally:
            if process.poll() is None:
                # The launcher leads its own session; kill every member of it.
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        log.seek(0)
        return PipelineRun(run_id, poll, log.read()[:OUTPUT_HEAD_CHARS])
