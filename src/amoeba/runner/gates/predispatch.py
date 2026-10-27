"""Pre-dispatch checks: what a checkout and CF's gate must say before a launch (D5, D6).

Every rule here is pure. ``Ok`` carries the evidence a launch's journal entry records
as ``dispatch_check``; ``Block`` is a node block the planner turns into a
``BlockDispatch``. This module imports nothing from ``decide.py``: the action type
imports it, not the other way around.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from amoeba.runner.faults import FaultKind
from amoeba.runner.gates.cf_status import (
    ENTRY_GATE,
    CFActiveSlice,
    GatePosition,
    position_of,
)
from amoeba.runner.git_read import GitStatus
from amoeba.runner.lifecycle.steps import PIPELINE_P6, LifecycleStep
from amoeba.upstream.context_forge import parse_slice_stem

#: How many changed paths a ``checkout_dirty`` block lists; the count is always given.
DIRTY_PATHS_SHOWN: Final = 20

#: Block payload keys (D5, D11).
PAYLOAD_BRANCH: Final = "branch"
PAYLOAD_TARGET: Final = "target"
PAYLOAD_ALLOWED: Final = "allowed"
PAYLOAD_PATHS: Final = "paths"
PAYLOAD_PATH_COUNT: Final = "path_count"
PAYLOAD_DECISIONS: Final = "decisions"
PAYLOAD_POSITION: Final = "position"
PAYLOAD_GATE_STATUS: Final = "status"
PAYLOAD_REVIEW_TYPE: Final = "review_type"
PAYLOAD_RATIONALE: Final = "rationale"

#: ``Ok`` evidence keys.
EVIDENCE_GATE_STATUS: Final = "gate_status"
EVIDENCE_GATE_REVIEW_TYPE: Final = "gate_review_type"
#: Set when the PM accepted a step CF still fails: the id of the check recording it.
EVIDENCE_DISAGREEMENT_CHECK: Final = "disagreement_check"


@dataclass(frozen=True)
class Ok:
    """The checkout and the gate allow the dispatch; ``evidence`` says on what basis."""

    evidence: Mapping[str, object]


@dataclass(frozen=True)
class Block:
    """The dispatch must not go ahead: block the node on a human, saying why."""

    fault_kind: FaultKind
    context: str
    payload: Mapping[str, object]


#: What the pre-dispatch checks decided for one candidate. A candidate with no entry
#: in the view's ``dispatch_checks`` has no result: its reads were cut off or failed.
type DispatchCheck = Ok | Block


@dataclass(frozen=True)
class NoResult:
    """The gate read is about another slice: nothing to decide, and no fault (D5)."""


@dataclass(frozen=True)
class Disagreement:
    """The PM accepted the predecessor and CF's gate still fails (D7).

    The caller records the disagreement as a check, then goes on with ``ok``: the
    accept stands, and dispatch is not held back by it.
    """

    ok: Ok
    gate: CFActiveSlice


def allowed_branches(pipeline: str, target: str, slice_index: int) -> tuple[str, ...]:
    """The branches a pipeline may start on, for a message: the target, and for ``P6``
    this slice's own branch (any branch named ``{index}-slice.*``)."""
    if pipeline == PIPELINE_P6:
        return (target, f"{slice_index}-slice.*")
    return (target,)


def is_slice_branch(branch: str, slice_index: int) -> bool:
    """Whether ``branch`` is the slice's own branch: ``{index}-slice.*`` (D6).

    ``parse_slice_stem`` reads only the last path part, so a "/"-prefixed name is
    never the slice's own branch: Squadron names slice branches with no prefix.
    """
    stem = parse_slice_stem(branch)
    return stem is not None and "/" not in branch and stem.index == slice_index


def _is_allowed(branch: str, pipeline: str, target: str, slice_index: int) -> bool:
    if branch == target:
        return True
    return pipeline == PIPELINE_P6 and is_slice_branch(branch, slice_index)


def branch_rule(
    status: GitStatus,
    target: str,
    pipeline: str,
    slice_index: int,
    *,
    resume: bool,
) -> Block | None:
    """The git half of the pre-dispatch check; the first rule that applies decides.

    1. A detached HEAD blocks. 2. A branch outside the pipeline's allowed set blocks
    (D6). 3. A launch or reissue with any changed, staged, unmerged or untracked
    path blocks; a resume never does, because a paused run's tree may hold its own
    uncommitted work (D5).
    """
    allowed = allowed_branches(pipeline, target, slice_index)
    if status.branch is None:
        return Block(
            FaultKind.CHECKOUT_BRANCH,
            "the checkout is on a detached HEAD, not on a branch",
            {PAYLOAD_BRANCH: None, PAYLOAD_TARGET: target, PAYLOAD_ALLOWED: allowed},
        )
    if not _is_allowed(status.branch, pipeline, target, slice_index):
        return Block(
            FaultKind.CHECKOUT_BRANCH,
            f"the checkout is on {status.branch!r}; {pipeline} may start only on "
            f"{' or '.join(allowed)}",
            {
                PAYLOAD_BRANCH: status.branch,
                PAYLOAD_TARGET: target,
                PAYLOAD_ALLOWED: allowed,
            },
        )
    if not resume and status.dirty:
        shown = status.dirty[:DIRTY_PATHS_SHOWN]
        return Block(
            FaultKind.CHECKOUT_DIRTY,
            f"the checkout has {len(status.dirty)} changed path(s): "
            + ", ".join(shown),
            {PAYLOAD_PATHS: list(shown), PAYLOAD_PATH_COUNT: len(status.dirty)},
        )
    return None


def entry_gate(
    step: LifecycleStep,
    active_slice: CFActiveSlice,
    slice_index: int,
    *,
    accepted: bool,
) -> Ok | Block | NoResult | Disagreement:
    """The gate half of the pre-dispatch check for ``tasks`` and ``implementation``.

    ``accepted`` says the PM accepted the predecessor in the store. CF at the entry
    gate then is the disagreement D7 records; otherwise it blocks.

    Raises:
        ValueError: ``step`` has no entry gate.
    """
    gate = ENTRY_GATE.get(step)
    if gate is None:
        raise ValueError(f"step {step.value} has no entry gate")
    if active_slice.index != slice_index:
        return NoResult()
    position = position_of(active_slice)
    info = active_slice.gate_info
    ok = Ok(
        {
            EVIDENCE_GATE_STATUS: active_slice.status,
            EVIDENCE_GATE_REVIEW_TYPE: None if info is None else info.review_type,
        }
    )
    if position is GatePosition.PENDING_DECISION:
        return _pending_decision(active_slice)
    if position.on_scale and position > gate:
        return ok
    if position is gate and accepted:
        return Disagreement(ok, active_slice)
    return _gate_blocks(step, active_slice, position)


def _pending_decision(active_slice: CFActiveSlice) -> Block:
    decisions = [
        {"heading": item.heading, "line": item.line}
        for item in active_slice.pending_decisions or ()
    ]
    return Block(
        FaultKind.PENDING_DECISION,
        "the design holds a decision the PM owes",
        {PAYLOAD_DECISIONS: decisions},
    )


def _gate_blocks(
    step: LifecycleStep, active_slice: CFActiveSlice, position: GatePosition
) -> Block:
    info = active_slice.gate_info
    return Block(
        FaultKind.CF_GATE_BLOCKS,
        f"CF's gate before {step.value} has not cleared: {active_slice.status}",
        {
            PAYLOAD_POSITION: position.name,
            PAYLOAD_GATE_STATUS: active_slice.status,
            PAYLOAD_REVIEW_TYPE: None if info is None else info.review_type,
            PAYLOAD_RATIONALE: None if info is None else info.rationale,
        },
    )
