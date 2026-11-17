"""``handle_pause``: answer an agent's question and resume the run, or record it as
waiting on the PM (slice 223, D3 to D8).

The entry point. ``pause_eligibility`` decides whether the pause is this member's to
handle; the existing row picks the path (D4): none claims and answers it
(``pause_claim``), or holds it on the request its marker names (``pause_held``, slice
242), anything else is ``pause_existing``. ``SkipReason`` and
``HandlePauseResult`` are re-exported here, so the design's import path holds.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.message_sweep import sweep_messages
from amoeba.operations.pause_claim import start_new_claim
from amoeba.operations.pause_class import PauseClass, classify_pause
from amoeba.operations.pause_eligibility import Skip, check_eligibility
from amoeba.operations.pause_existing import checkout_of, handle_existing
from amoeba.operations.pause_held import hold_new, link_for
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    SkipReason,
)
from amoeba.operations.pause_results import PauseTarget, skipped
from amoeba.operations.question_sweep import sweep_note, sweep_run
from amoeba.operations.request_link import NoLink
from amoeba.operations.request_release import start_ended_held
from amoeba.store.answers import latest_answer
from amoeba.store.errors import StoreError, StoreRowError
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_outcome import PollFailure, RunOutcomeDocument

logger = logging.getLogger(__name__)

__all__ = [
    "HandlePauseOutcome",
    "HandlePauseResult",
    "SkipReason",
    "handle_pause",
]


def handle_pause(
    store: Store,
    config: UserConfig,
    run_id: str,
    *,
    directory: Path,
    deps: Deps,
) -> HandlePauseResult:
    """Handle ``run_id``'s pause, called from the run's own ``directory``.

    Raises:
        SquadronError: ``sq`` or the run file gave no usable answer.
        ContextForgeError: ``cf`` gave no usable answer.
        ConfigError: The member refers to an authorize key the config lacks.
        StoreError: The store cannot be used (a failure of the final prune is a note
            in ``detail`` instead).
    """
    try:
        polled = deps.poll_run(run_id)
        if isinstance(polled, PollFailure):
            raise SquadronError(polled.reason)
        # Before eligibility and so before every skip: closing this run's older open
        # questions depends only on the run id and what Squadron says, never the
        # directory.
        swept = sweep_run(store, config, run_id, polled, deps.clock())
        result = _handle_polled(store, config, run_id, directory, deps, polled)
        # Last, after any resume, so pruning never delays one (228 D9).
        notes = [
            note
            for note in (
                sweep_note(swept),
                _prune_note(store, config, deps),
                _message_sweep_note(store, config, deps),
            )
            if note is not None
        ]
    finally:
        # Last of all, and on every path, a raise included: start the held questions
        # whose request ended, so a batch over the per-call cap drains through each
        # child's own call even when that call fails (242 D7). Never raises.
        start_ended_held(store, config, deps)
    if not notes:
        return result
    detail = "; ".join(([] if result.detail is None else [result.detail]) + notes)
    return replace(result, detail=detail)


def _prune_note(store: Store, config: UserConfig, deps: Deps) -> str | None:
    """What pruning could not do, as a note. A store failure here is a note, not an
    error: the result is already decided, and a resume may already have been
    delivered, so raising would report a failure for work that happened."""
    try:
        pruned = deps.prune(store, now=deps.clock(), after_days=config.prune_after_days)
    except StoreError as error:
        logger.exception("prune failed after handling the pause")
        return f"prune: {error}"
    return pruned.note()


def _message_sweep_note(store: Store, config: UserConfig, deps: Deps) -> str | None:
    """What the message sweep could not do, as a note, for the reason the prune's is
    one: the result is already decided. A busy store is already a problem text; any
    other store failure is logged and noted here."""
    try:
        return sweep_messages(store, config, deps.clock())
    except StoreError as error:
        logger.exception("the message sweep failed after handling the pause")
        return f"message sweep: {error}"


def _handle_polled(  # noqa: PLR0913 - the pieces of one call
    store: Store,
    config: UserConfig,
    run_id: str,
    directory: Path,
    deps: Deps,
    polled: RunOutcomeDocument,
) -> HandlePauseResult:
    checked = check_eligibility(store, run_id, directory, deps, polled)
    if isinstance(checked, Skip):
        return skipped(checked.reason, None, None, checked.detail)
    target = PauseTarget(
        key=checked.key,
        question=checked.question,
        checkout=directory,
        member=checked.member,
        run_facts=checked.run_facts,
    )
    existing = checked.existing
    latest = None
    if existing is not None and existing.state is QuestionState.ANSWERED:
        with store.read() as transaction:
            latest = latest_answer(transaction, checked.key)
        if latest is None:
            raise StoreRowError(
                f"question {checked.key} is answered but has no answer row"
            )
    pause_class = classify_pause(
        checked.observed,
        existing,
        latest,
        checked.run_facts,
        config.answering_wait_seconds,
        deps.clock(),
    )
    if existing is None:
        if pause_class is not PauseClass.UNHANDLED:
            raise ValueError(f"{pause_class} should have been skipped as ineligible")
        # A question naming a request this repo sent waits on it (242 D1).
        link = link_for(store, target)
        if isinstance(link, NoLink):
            return start_new_claim(store, config, deps, target)
        return hold_new(store, config, deps, target, link)
    # A claimed question stays in the checkout it was claimed in, wherever it is
    # handled from.
    at_claim = replace(target, checkout=checkout_of(existing))
    return handle_existing(store, config, deps, at_claim, existing, pause_class, latest)
