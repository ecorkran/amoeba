"""One answering run: scratch, start and wait (slice 223, D6).

The claim is inserted before the run starts, so the run id is minted and the scratch
made first (``make_scratch``). ``start`` builds the one command line, always carrying
the opt-out of Squadron's pause command, and starts it detached; ``wait`` waits on the
child process (never on a blocking ``sq runs wait``) and polls once. Every failure a
run can have comes back as a ``Declined`` value, so the claim never hangs. No store
transaction is open while anything here runs. ``answering_settle`` decides what a
finished run means.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from amoeba.answering.decide import Declined
from amoeba.answering.inputs import BarredItem, QuestionInput
from amoeba.answering.launch import prepare_scratch_directory
from amoeba.answering.pipeline_file import (
    ANSWER_MODEL_PARAM,
    CHECK_MODEL_PARAM,
    answering_pipeline_path,
)
from amoeba.answering.settings import AnswererSettings
from amoeba.answering.values import AnsweringEvidence, DeclineReason
from amoeba.operations.deps import Deps
from amoeba.operations.processes import WaitableChild, terminate_group
from amoeba.store.models import QuestionKey
from amoeba.upstream.bounded_text import cut_to_bound
from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.launch import (
    LaunchError,
    LaunchLogs,
    build_argv,
    stderr_tail,
)
from amoeba.upstream.squadron.run_outcome import (
    SQ_USAGE_ERROR_EXIT_CODE,
    Finished,
    LaunchFailed,
    PollFailure,
    RunEnded,
    RunOutcome,
    RunVanished,
)

#: ``sq run``'s opt-out of the pipeline's pause command (Squadron #302). An answering
#: run always passes it: it must never start the command that answers pauses.
NO_PAUSE_HOOK_FLAG: Final = "--no-pause-hook"

#: Log subdirectory of an answering run: ``<logs>/answering/<id>.{stdout,stderr}.log``.
ANSWERING_LOG_DIRECTORY: Final = "answering"
STDOUT_LOG_SUFFIX: Final = ".stdout.log"
STDERR_LOG_SUFFIX: Final = ".stderr.log"


@dataclass(frozen=True)
class ScratchFailure:
    """The scratch directory could not be made; ``detail`` is the OS error."""

    detail: str


@dataclass(frozen=True)
class Claim:
    """What the settle of one claimed question needs: the claim and its question."""

    key: QuestionKey
    answering_run_id: str
    #: The question text, as stored (the gate screens it).
    question: str
    passage_ids: frozenset[str]
    settings: AnswererSettings
    #: ``answering_wait_seconds`` from the config: how long the run may take.
    wait_seconds: float


def scratch_path(answering_dir: Path, answering_run_id: str) -> Path:
    """Where a run's scratch lives. Derived, never stored (slice 223, State)."""
    return answering_dir / answering_run_id


def make_scratch(  # noqa: PLR0913 - one argument per fact of the scratch
    answering_dir: Path,
    run_id: str,
    question: QuestionInput,
    passages_markdown: str,
    max_cost_usd: float,
    not_authorized: Sequence[BarredItem],
) -> Path | ScratchFailure:
    """Create ``<answering_dir>/<run_id>`` exclusively and fill it.

    ``not_authorized`` is always the member's own list, so ``not_authorized.md``
    holds it (an empty list renders the "nothing barred" line).
    """
    scratch = scratch_path(answering_dir, run_id)
    problem = prepare_scratch_directory(
        scratch,
        question,
        passages_markdown,
        max_cost_usd,
        not_authorized=not_authorized,
    )
    return scratch if problem is None else ScratchFailure(problem)


def answering_logs(logs_dir: Path, run_id: str) -> LaunchLogs:
    """The log files of an answering run, named from its run id."""
    directory = logs_dir / ANSWERING_LOG_DIRECTORY
    return LaunchLogs(
        stdout=directory / f"{run_id}{STDOUT_LOG_SUFFIX}",
        stderr=directory / f"{run_id}{STDERR_LOG_SUFFIX}",
    )


def answering_argv(run_id: str, settings: AnswererSettings) -> list[str]:
    """``sq run <answering.yaml> <answer_model> --run-id <id> -p check-model=<m>``
    plus the pause-hook opt-out.

    Raises:
        ValueError: A model alias Squadron would split or read as an option.
    """
    argv = build_argv(
        str(answering_pipeline_path()),
        run_id,
        {
            ANSWER_MODEL_PARAM: settings.answer_model,
            CHECK_MODEL_PARAM: settings.check_model,
        },
        target_key=ANSWER_MODEL_PARAM,
    )
    return [*argv, NO_PAUSE_HOOK_FLAG]


def _declined(reason: DeclineReason, detail: str) -> Declined:
    return Declined(reason, cut_to_bound(detail), AnsweringEvidence())


def start(
    deps: Deps, run_id: str, scratch: Path, settings: AnswererSettings
) -> WaitableChild | Declined:
    """Start the answering run detached in its scratch directory."""
    try:
        argv = answering_argv(run_id, settings)
    except ValueError as error:
        # Specific: a model alias Squadron cannot take; the claim records why.
        return _declined(DeclineReason.ANSWERING_LAUNCH_FAILED, str(error))
    started = deps.spawn(argv, scratch, answering_logs(deps.logs_dir, run_id))
    if isinstance(started, LaunchError):
        return _declined(DeclineReason.ANSWERING_LAUNCH_FAILED, started.detail)
    return started


def wait(
    deps: Deps,
    child: WaitableChild,
    run_id: str,
    wait_seconds: float,
) -> Finished | Declined:
    """Wait up to ``wait_seconds`` for the child to exit, then read the run once.

    On timeout the child's process group is stopped and the result is
    ``answering_run_stalled``. A poll that cannot be read is
    ``answering_run_failed``, so the claim does not hang.
    """
    try:
        exit_code = child.wait(timeout=wait_seconds)
    except subprocess.TimeoutExpired:
        # Expected: the run took too long; stop it and say so.
        terminate_group(child)
        return _declined(
            DeclineReason.ANSWERING_RUN_STALLED,
            f"no result after {wait_seconds:g} seconds",
        )
    polled = deps.poll_run(run_id)
    if isinstance(polled, PollFailure):
        return _declined(DeclineReason.ANSWERING_RUN_FAILED, polled.reason)
    if polled.outcome is not RunOutcome.NOT_FOUND:
        return RunEnded(polled)
    # The child is gone and Squadron has no such run: it never started one.
    if exit_code == 0:
        return RunVanished()
    return LaunchFailed(
        _launch_failure(exit_code),
        exit_code,
        _stderr_tail_or_note(answering_logs(deps.logs_dir, run_id).stderr),
    )


def _launch_failure(exit_code: int) -> LaunchFailure:
    if exit_code == SQ_USAGE_ERROR_EXIT_CODE:
        return LaunchFailure.USAGE_ERROR
    return LaunchFailure.EXITED_BEFORE_LINE


def _stderr_tail_or_note(path: Path) -> str:
    try:
        return stderr_tail(path)
    except OSError as error:
        # Expected: the log is unreadable; the decline says so instead of the tail.
        return f"stderr log unreadable: {error}"
