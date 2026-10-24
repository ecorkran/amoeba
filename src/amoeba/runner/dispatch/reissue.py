"""Reissuing a launch that never started (D9, issue #9).

Recovery resolves an ``sq_run`` entry ``not_applied`` when, after the launch grace
period, Squadron has no state for its run id. The step is then ``REISSUE``, and the
planner asks for the same launch again under the same run id. Because Squadron
refuses an id that already has state, a second launch can never produce a second run;
what the reissue guards against is launching over a run that did start and whose state
was later removed, which would repeat work. So, in order:

1. The old attempt's launch log is checked. Squadron prints ``run_id=<id>`` before
   its first step, so a log with that exact line means the run began: the step blocks
   on a human (``started_before_crash``) and nothing is launched. A log that exists
   and cannot be read blocks too, naming the error. No log, or a log without the
   line, means no work ran: continue.
2. A new ``sq_run`` entry is journaled with the same pipeline, params, checkout and
   run id, plus ``reissue_of``. The old entry has no run id in its result, so
   120's claimed-id guard does not refuse the id.
3. The run id is polled once. A run state that appeared in the meantime (a slow
   launch) is adopted: the new entry is in flight and nothing is launched.
4. Otherwise the caller launches it, as for any launch. Should Squadron refuse the id
   because a run appeared in between, the child exits without the line and the
   observer's single poll finds the state, so the run is observed, not failed.

The pointer is not re-written: the relaunch repeats the same command, and Squadron's
phase step sets the slice pointer itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from amoeba.process import PollFailure, RunOutcome, RunPoll
from amoeba.runner.decide import LaunchRun
from amoeba.runner.ingest.outcome import (
    PAYLOAD_REASON,
    PAYLOAD_RUN_ID,
    REASON_STARTED_BEFORE_CRASH,
    BlockPlan,
    cut_to_bound,
)
from amoeba.runner.ingest.record import block_once
from amoeba.runner.launch import (
    PARAM_PARAMS,
    PARAM_PIPELINE,
    PARAM_REISSUE_OF,
    log_paths,
    stderr_confirms,
)
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    BlockedKind,
    CommandKind,
    JournalEntry,
    Store,
)


@dataclass(frozen=True)
class ReissueBlocked:
    """The step was blocked on a human; nothing was journaled or launched."""

    reason: str


@dataclass(frozen=True)
class ReissueAdopted:
    """A run state exists for the id: the new entry is in flight, nothing launched."""

    entry: JournalEntry


@dataclass(frozen=True)
class ReissueLaunch:
    """The new entry is journaled and ready to launch."""

    entry: JournalEntry


type ReissueDecision = ReissueBlocked | ReissueAdopted | ReissueLaunch


def begin_reissue(
    store: Store,
    action: LaunchRun,
    supervisor_dir: Path,
    poll: Callable[[str], RunPoll],
) -> ReissueDecision:
    """Run D9's steps 1-3 for a ``LaunchRun`` that carries ``reissue_of``."""
    if action.run_id is None or action.reissue_of is None:
        raise ValueError(f"launch for node {action.node_id} is not a reissue")
    refusal = _old_attempt_refusal(supervisor_dir, action.reissue_of, action.run_id)
    if refusal is not None:
        _block(store, action, refusal)
        return ReissueBlocked(refusal)
    entry = store.journal_issue(
        action.node_id,
        kind=CommandKind.SQ_RUN,
        parameters={
            PARAM_PIPELINE: action.pipeline,
            PARAM_PARAMS: dict(action.params),
            PARAM_RUN_ID: action.run_id,
            PARAM_CHECKOUT: str(action.checkout),
            PARAM_REISSUE_OF: action.reissue_of,
        },
    )
    if _run_exists(poll(action.run_id)):
        return ReissueAdopted(entry)
    return ReissueLaunch(entry)


def _old_attempt_refusal(
    supervisor_dir: Path, old_entry_id: str, run_id: str
) -> str | None:
    """Why the old attempt's log forbids a relaunch, or ``None`` to go on."""
    log = log_paths(supervisor_dir, old_entry_id).stderr
    try:
        began = stderr_confirms(log, run_id)
    except FileNotFoundError:
        # Specific: the old attempt left no log, so no work ran. An answer.
        return None
    except OSError as error:
        # Specific: a log that exists and cannot be read. A person looks.
        return f"the launch log of entry {old_entry_id} is unreadable: {error}"
    if began:
        return REASON_STARTED_BEFORE_CRASH
    return None


def _run_exists(polled: RunPoll) -> bool:
    """Whether Squadron has any state for the run. A failed poll says no.

    A poll that failed tells nothing about the run, and launching is safe either way:
    Squadron refuses an id that already has state.
    """
    if isinstance(polled, PollFailure):
        return False
    return polled.outcome is not RunOutcome.NOT_FOUND


def _block(store: Store, action: LaunchRun, refusal: str) -> None:
    """Block the step on a human, saying why the reissue was refused."""
    started = refusal == REASON_STARTED_BEFORE_CRASH
    reason = cut_to_bound(refusal)
    context = (
        f"run {action.run_id} began before the crash and its state is gone; "
        "it is not launched again"
        if started
        else reason
    )
    block_once(
        store,
        action.node_id,
        BlockPlan(
            BlockedKind.HUMAN,
            context,
            {PAYLOAD_REASON: reason, PAYLOAD_RUN_ID: action.run_id},
        ),
    )
