"""Two members, a request between them, and a run held on it (slice 242, D5, task 8.1).

The pause tier's member plays ``sq-s``, the repo whose run asks; the messaging tier's
``build_repo`` adds ``cf-s``, the repo the request goes to, in the same throwaway
program, store and Context Forge data directory. Everything runs the real ``sq``,
``cf`` and ``amoeba`` with the configured models. The harness sends the request, runs
``amoeba handle-pause`` once for the held first call (the hook's part), replies from
``cf-s`` through the CLI and then only polls: the reply starts ``handle-pause`` itself.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from live_harness import PipelineRun, watch_run

from amoeba.operations.answering_run import PAUSE_COMMAND_OPT_OUT_FLAG
from amoeba.upstream.squadron.launch import build_argv
from amoeba.upstream.squadron.run_outcome import RunPoll, poll_run
from live.messaging.repos import FORGE_NAME, build_repo
from live.pause.harness import (
    ANSWERING_WAIT_SECONDS,
    LAUNCHER_EXIT_GRACE_SECONDS,
    PIPELINE_MODEL_PARAM,
    RESUME_WAIT_SECONDS,
    SQ_RUN_TIMEOUT_SECONDS,
    PauseWorld,
    inert_hook,
    result_of,
    run_amoeba,
    store_rows,
)

HOLD_PIPELINE: Final = Path(__file__).parent / "asks_request.yaml"
#: The pipeline parameter that carries the request id into the marker line.
REQUEST_PARAM: Final = "request"
POLL_INTERVAL_SECONDS: Final = 10.0
POLL_CALL_TIMEOUT_SECONDS: Final = 30.0
#: Room for the reply's start, ``handle-pause``'s own polls and process start-up.
AUTO_RESUME_MARGIN_SECONDS: Final = 180
#: How long the poll waits for the held question to end after the reply.
AUTO_RESUME_WAIT_SECONDS: Final = (
    ANSWERING_WAIT_SECONDS + RESUME_WAIT_SECONDS + AUTO_RESUME_MARGIN_SECONDS
)
#: Question states the poll stops at: answered, or not answered by the answerer.
QUESTION_ENDED_STATES: Final = frozenset({"answered", "waiting_on_pm", "closed"})


@dataclass(frozen=True)
class HoldWorld:
    """``asker`` is ``sq-s`` (its run is held); ``addressee`` is ``cf-s``."""

    asker: PauseWorld
    addressee: PauseWorld


@dataclass(frozen=True)
class Observed:
    """One read of everything the poll watches."""

    state: str | None
    waiting_reason: str | None
    request_id: str | None
    resume_outcome: str | None
    poll: RunPoll
    decisions: dict[str, Any]


def build_hold_world(parent: Path, pause_world: PauseWorld) -> HoldWorld:
    """``sq-s`` with the hook made inert, and ``cf-s`` added to its program.

    The inert hook keeps the installed ``amoeba`` from handling the run behind the
    test's back; every call the harness makes, and the child the reply starts, uses
    the absolute script path.
    """
    asker = inert_hook(pause_world)
    return HoldWorld(asker=asker, addressee=build_repo(parent, asker, FORGE_NAME))


def amoeba_document(world: PauseWorld, *arguments: str) -> dict[str, Any]:
    """``amoeba <arguments> -j`` in ``world``'s checkout; exit 0 or the test fails."""
    completed = run_amoeba(world, *arguments)
    assert completed.returncode == 0, (
        f"amoeba {' '.join(arguments)} exited {completed.returncode}\n"
        f"{completed.stdout}\n{completed.stderr}"
    )
    return dict(result_of(completed))


def send_request(hold: HoldWorld, request_id: str) -> None:
    amoeba_document(
        hold.asker,
        "send",
        "--id",
        request_id,
        "--to",
        FORGE_NAME,
        "--subject",
        "Add a release-notes section to the shared guide",
        "--body",
        "Please add a release-notes section to the shared guide and say what this "
        "repository should do once it is in.",
    )


def start_held_pause(hold: HoldWorld, run_id: str, request_id: str) -> PipelineRun:
    """Run ``asks_request.yaml`` in ``sq-s`` until it pauses on the marked question.

    The run opts out of the pause command, so only the harness's own first call
    handles the pause.
    """
    params = {
        PIPELINE_MODEL_PARAM: hold.asker.settings.answer_model,
        REQUEST_PARAM: request_id,
    }
    argv = build_argv(
        str(HOLD_PIPELINE), run_id, params, target_key=PIPELINE_MODEL_PARAM
    )
    return watch_run(
        [*argv, PAUSE_COMMAND_OPT_OUT_FLAG],
        run_id,
        hold.asker.repo,
        SQ_RUN_TIMEOUT_SECONDS,
        LAUNCHER_EXIT_GRACE_SECONDS,
        hold.asker.environ,
    )


def handle_pause_once(hold: HoldWorld, run_id: str) -> dict[str, Any]:
    """The hook's part: one ``amoeba handle-pause`` in ``sq-s``."""
    return amoeba_document(hold.asker, "handle-pause", run_id)


def reply_done(hold: HoldWorld, request_id: str, result: str) -> None:
    """``cf-s`` accepts the request, then marks it done with ``result``."""
    amoeba_document(hold.addressee, "reply", request_id, "accept")
    amoeba_document(hold.addressee, "reply", request_id, "done", "--text", result)


def observe(hold: HoldWorld, run_id: str) -> Observed:
    rows = store_rows(
        hold.asker,
        "SELECT state, waiting_reason, request_id FROM questions WHERE run_id = ?",
        (run_id,),
    )
    state = reason = request = None
    if rows:
        ((state, reason, request),) = rows
    outcomes = store_rows(
        hold.asker,
        "SELECT resume_outcome FROM answers WHERE run_id = ? ORDER BY seq",
        (run_id,),
    )
    return Observed(
        state=None if state is None else str(state),
        waiting_reason=None if reason is None else str(reason),
        request_id=None if request is None else str(request),
        resume_outcome=(
            None if not outcomes or outcomes[-1][0] is None else str(outcomes[-1][0])
        ),
        poll=poll_run(run_id, timeout_seconds=POLL_CALL_TIMEOUT_SECONDS),
        decisions=amoeba_document(hold.asker, "decisions"),
    )


def held_question_ended(observed: Observed) -> bool:
    """The question left the hold and, if answered, the resume has an outcome."""
    if observed.state not in QUESTION_ENDED_STATES:
        return False
    return observed.state != "answered" or observed.resume_outcome is not None


def poll_until(
    hold: HoldWorld,
    run_id: str,
    ended: Callable[[Observed], bool] = held_question_ended,
) -> Observed:
    """Read every ``POLL_INTERVAL_SECONDS`` until ``ended``; at
    ``AUTO_RESUME_WAIT_SECONDS`` fail with the last read."""
    deadline = time.monotonic() + AUTO_RESUME_WAIT_SECONDS
    observed = observe(hold, run_id)
    while not ended(observed):
        if time.monotonic() >= deadline:
            raise AssertionError(
                f"the held question of run {run_id} had not ended after "
                f"{AUTO_RESUME_WAIT_SECONDS}s; last read: {observed}"
            )
        time.sleep(POLL_INTERVAL_SECONDS)
        observed = observe(hold, run_id)
    return observed
