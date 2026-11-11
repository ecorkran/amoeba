"""``handle_pause``: answer an agent's question and resume the run, or record it as
waiting on the PM (slice 223, D3 to D8).

The entry point. ``pause_eligibility`` decides whether the pause is this member's to
handle; the existing row picks the path (D4): none claims and answers it
(``pause_claim``), anything else is ``pause_existing``. ``SkipReason`` and
``HandlePauseResult`` are re-exported here, so the design's import path holds.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.pause_claim import start_new_claim
from amoeba.operations.pause_class import PauseClass, classify_pause
from amoeba.operations.pause_eligibility import Skip, check_eligibility
from amoeba.operations.pause_existing import checkout_of, handle_existing
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    SkipReason,
)
from amoeba.operations.pause_results import PauseTarget, skipped
from amoeba.store.answers import latest_answer
from amoeba.store.errors import StoreRowError
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState

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
        StoreError: The store cannot be used.
    """
    checked = check_eligibility(store, run_id, directory, deps)
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
        return start_new_claim(store, config, deps, target)
    # A claimed question stays in the checkout it was claimed in, wherever it is
    # handled from.
    at_claim = replace(target, checkout=checkout_of(existing))
    return handle_existing(store, config, deps, at_claim, existing, pause_class, latest)
