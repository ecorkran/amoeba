"""Whether the PM accepted a step's completed outcome in the store (slice 128, D7).

127 made the accept identifiable: the step's latest blocked state holds an applied
``accept``, and the step's latest ``sq_run`` entry is the completed outcome it
accepted. A loop accept is not counted: it resumes the paused run, so the latest run
entry is a continuation (issue #17 defers counting it). Pure, and defined once.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from amoeba.process import RunOutcome
from amoeba.runner.gates.cf_status import CFActiveSlice
from amoeba.runner.gates.checks import RunnerCheck, check_id, runner_provenance
from amoeba.runner.ingest.record import RESULT_OUTCOME, RESULT_VERDICT_IDS
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.resolutions.vocabulary import ResolutionDecision
from amoeba.store import (
    PARAM_CONTINUATION,
    BlockedState,
    CheckInput,
    CheckOutcome,
    JournalEntry,
    RecordSource,
    ResolutionOutcome,
    latest_run_entry,
)


@dataclass(frozen=True)
class AcceptedOutcome:
    """The PM's accept: which blocked state, which run entry, which reviews."""

    blocked_state_id: str
    entry_id: str
    verdict_ids: tuple[str, ...]


def accepted_by_pm(
    entries: Sequence[JournalEntry], latest_blocked: BlockedState | None
) -> AcceptedOutcome | None:
    """The accepted outcome of a step, or ``None`` if the PM accepted none.

    ``entries`` are the step's journal entries, oldest first; ``latest_blocked`` its
    most recent blocked state, resolved or not.
    """
    if latest_blocked is None or latest_blocked.resolution is None:
        return None
    if latest_blocked.runner_outcome is not ResolutionOutcome.APPLIED:
        return None
    if latest_blocked.resolution.decision != ResolutionDecision.ACCEPT.value:
        return None
    entry = latest_run_entry(entries)
    if entry is None or PARAM_CONTINUATION in entry.parameters:
        return None
    result = entry.result or {}
    if result.get(RESULT_OUTCOME) != RunOutcome.COMPLETED.value:
        return None
    return AcceptedOutcome(latest_blocked.id, entry.id, _verdict_ids(result))


def _verdict_ids(result: Mapping[str, object]) -> tuple[str, ...]:
    raw = result.get(RESULT_VERDICT_IDS)
    if not isinstance(raw, list):
        return ()
    items = cast("list[object]", raw)
    return tuple(item for item in items if isinstance(item, str))


def disagreement_check(
    accepted: AcceptedOutcome,
    slice_node_id: str,
    accepted_step: LifecycleStep,
    gate: CFActiveSlice,
    amoeba_version: str,
) -> CheckInput:
    """The record that the PM accepted a step whose CF gate still fails (D7).

    One gate was evaluated, so ``examined_count`` is 1. The id is fixed by the
    accepted entry, so a rerun or a later tick that reads the gate again records
    nothing new.
    """
    info = gate.gate_info
    return CheckInput(
        id=check_id(accepted.entry_id, RunnerCheck.CF_GATE_ACCEPT_DISAGREEMENT),
        node_id=slice_node_id,
        name=RunnerCheck.CF_GATE_ACCEPT_DISAGREEMENT.value,
        outcome=CheckOutcome.FAILED,
        examined_count=1,
        provenance=runner_provenance(amoeba_version, RecordSource.COMMAND_OUTPUT, None),
        examined={
            "step": accepted_step.value,
            "cf_status": gate.status,
            "review_type": None if info is None else info.review_type,
            "rationale": None if info is None else info.rationale,
            "accepted_by": accepted.blocked_state_id,
            "verdict_ids": list(accepted.verdict_ids),
        },
    )
