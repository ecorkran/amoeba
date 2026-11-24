"""``handle_pause``: answer an agent's question and resume the run, or record it as
waiting on the PM (slice 223, D3 to D8).

The entry point. ``pause_eligibility`` decides whether the pause is this member's to
handle; the existing row picks the path (D4): none claims and answers it
(``pause_claim``), or holds it on the request its marker names (``pause_held``, slice
242), anything else is ``pause_existing``. ``SkipReason`` and
``HandlePauseResult`` are re-exported here, so the design's import path holds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from amoeba.operations.deps import Deps
from amoeba.operations.pause_claim import start_new_claim
from amoeba.operations.pause_class import PauseClass, classify_pause
from amoeba.operations.pause_eligibility import (
    Eligible,
    Register,
    Skip,
    check_eligibility,
)
from amoeba.operations.pause_existing import checkout_of, handle_existing
from amoeba.operations.pause_held import hold_new, link_of
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    SkipReason,
)
from amoeba.operations.pause_results import PauseTarget, skipped
from amoeba.operations.question_sweep import sweep_note
from amoeba.operations.request_link import NoLink
from amoeba.operations.store_steps import Steps
from amoeba.store.errors import StoreRowError
from amoeba.store.vocabulary import QuestionState
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_outcome import PollFailure

__all__ = [
    "HandlePauseOutcome",
    "HandlePauseResult",
    "SkipReason",
    "handle_pause",
]


def handle_pause(  # noqa: PLR0913 - the edges one call is given
    steps: Steps,
    run_id: str,
    *,
    directory: Path,
    deps: Deps,
    register: Register,
    prune_note: Callable[[], str | None],
    after: Callable[[], None],
) -> HandlePauseResult:
    """Handle ``run_id``'s pause, called from the run's own ``directory``.

    Every store move is a step. ``register`` adds a project in no program (``add``'s
    defaults), ``prune_note`` runs the file clean-up and says what it could not do, and
    ``after`` starts the work that is waiting; it runs last on every path, a raise
    included, and never raises.

    Raises:
        SquadronError: ``sq`` or the run file gave no usable answer.
        ContextForgeError: ``cf`` gave no usable answer.
        ConfigError: The member refers to an authorize key the config lacks.
        HubUnreachableError, HubRefusedError: A step got no reply, or was refused.
        StoreError: The local store cannot be used.
    """
    try:
        polled = deps.poll_run(run_id)
        if isinstance(polled, PollFailure):
            raise SquadronError(polled.reason)
        checked = check_eligibility(steps, run_id, directory, deps, polled, register)
        if isinstance(checked, Skip):
            result = skipped(checked.reason, None, None, checked.detail)
            swept = checked.swept
        else:
            result = _handle_checked(steps, deps, directory, checked)
            swept = checked.begun.swept
        # Last, after any resume, so pruning never delays one (228 D9).
        notes = [note for note in (sweep_note(swept), prune_note()) if note is not None]
    finally:
        after()
    if not notes:
        return result
    detail = "; ".join(([] if result.detail is None else [result.detail]) + notes)
    return replace(result, detail=detail)


def _handle_checked(
    steps: Steps, deps: Deps, directory: Path, checked: Eligible
) -> HandlePauseResult:
    target = PauseTarget(
        key=checked.key,
        question=checked.question,
        checkout=directory,
        member=checked.member,
        cf_project_id=checked.cf_project_id,
        run_facts=checked.run_facts,
    )
    existing = checked.existing
    begun = checked.begun
    latest = begun.latest_answer
    if existing is not None and existing.state is QuestionState.ANSWERED:
        if latest is None:
            raise StoreRowError(
                f"question {checked.key} is answered but has no answer row"
            )
    pause_class = classify_pause(
        checked.observed, existing, latest, checked.run_facts, begun.claim_stale
    )
    if existing is None:
        if pause_class is not PauseClass.UNHANDLED:
            raise ValueError(f"{pause_class} should have been skipped as ineligible")
        # A question naming a request this repo sent waits on it (242 D1).
        link = link_of(begun)
        if isinstance(link, NoLink):
            return start_new_claim(steps, deps, target, begun)
        return hold_new(steps, deps, target, begun, link)
    # A claimed question stays in the checkout it was claimed in, wherever it is
    # handled from.
    at_claim = replace(target, checkout=checkout_of(existing))
    return handle_existing(steps, deps, at_claim, begun, existing, pause_class, latest)
