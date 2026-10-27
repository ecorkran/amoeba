"""A merge is observed in git by the reachability of the head ``P6`` left (D9).

The Runner never merges. Under the ``human`` policy the PM does; under ``auto`` ``P6``
did. Either way the Runner reads whether the head ``P6`` recorded is reachable from
the target, and only then completes the ``merge`` step. Reachability, not the branch
name, decides: deleting the slice branch after merging, or fix-up commits before it,
are still observed; a squash merge is not. :func:`merge_state` is pure;
:func:`observe_merges` does the reads under ``TickBudget``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.dispatch.params import PARAM_MERGE_POLICY
from amoeba.runner.faults import Fault, FaultKind, TickFaults
from amoeba.runner.gates.cf_reads import ReadFailure, read_target
from amoeba.runner.gates.merge_observation import (
    Merged,
    MergeObservation,
    NotMerged,
    Unobservable,
)
from amoeba.runner.gates.outcome_record import GIT_BRANCH, GIT_HEAD, OBS_GIT
from amoeba.runner.gates.predispatch import is_slice_branch
from amoeba.runner.git_read import GitReadFailure, git_read, is_ancestor_args
from amoeba.runner.ingest.record import RESULT_OUTCOME, RESULT_OUTCOME_OBSERVATION
from amoeba.runner.launch import text_parameter
from amoeba.runner.lifecycle.completion import complete_step
from amoeba.runner.lifecycle.plan_read import CF_KEY_INTEGRATION_BRANCH
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.project_config import MergePolicy
from amoeba.store import (
    PARAM_CHECKOUT,
    CommandKind,
    JournalEntry,
    Node,
    NodeKind,
    NodeStatus,
    Store,
)

#: ``git merge-base --is-ancestor`` exits 0 when the head is reachable, 1 when not.
EXIT_REACHABLE: Final = 0
EXIT_NOT_REACHABLE: Final = 1

REASON_NO_RUN: Final = "no completed implementation run is recorded"
REASON_NO_GIT: Final = "the implementation run recorded no branch and head"
REASON_ON_TARGET: Final = (
    "the implementation run ended on a branch that is not the slice's own, "
    "so nothing was left to merge"
)


def _recorded_git(entry: JournalEntry) -> tuple[str | None, str | None]:
    """The branch and head the entry's outcome observation recorded."""
    observation = (entry.result or {}).get(RESULT_OUTCOME_OBSERVATION)
    if not isinstance(observation, dict):
        return None, None
    git = cast("dict[str, object]", observation).get(OBS_GIT)
    if not isinstance(git, dict):
        return None, None
    recorded = cast("dict[str, object]", git)
    branch, head = recorded.get(GIT_BRANCH), recorded.get(GIT_HEAD)
    return (
        branch if isinstance(branch, str) else None,
        head if isinstance(head, str) else None,
    )


def _policy(entry: JournalEntry) -> str:
    # An entry launched before slice 128 records no policy; every such launch ran with
    # merge=false (125), which is the human policy.
    recorded = entry.parameters.get(PARAM_MERGE_POLICY)
    return recorded if isinstance(recorded, str) else MergePolicy.HUMAN.value


def unobservable_reason(entry: JournalEntry | None, slice_index: int) -> str | None:
    """Why a merge cannot be observed from ``entry`` without any read, or ``None``."""
    if entry is None:
        return REASON_NO_RUN
    branch, head = _recorded_git(entry)
    if branch is None or head is None:
        return REASON_NO_GIT
    own = is_slice_branch(branch, slice_index)
    if _policy(entry) == MergePolicy.HUMAN.value and not own:
        return REASON_ON_TARGET
    return None


def merge_state(
    entry: JournalEntry | None, slice_index: int, ancestor_exit: int | None
) -> MergeObservation | None:
    """The merge observation for a slice (D9's table); ``None`` is a read failure.

    ``entry`` is the implementation step's latest completed ``sq_run`` entry, or
    ``None``. ``ancestor_exit`` is the exit code of ``merge-base --is-ancestor``, or
    ``None`` when it could not be run.
    """
    reason = unobservable_reason(entry, slice_index)
    if reason is not None:
        return Unobservable(reason)
    if entry is None or ancestor_exit is None:
        return None
    _, head = _recorded_git(entry)
    if head is None:
        return None
    if ancestor_exit == EXIT_REACHABLE:
        return Merged(head)
    if ancestor_exit == EXIT_NOT_REACHABLE:
        return NotMerged()
    return None


@dataclass(frozen=True)
class MergePass:
    """What one merge-observation pass found, wrote, and whether it was cut off."""

    observations: Mapping[str, MergeObservation]
    wrote: bool
    cut_off: bool


COMMAND_TARGET: Final = f"cf config get {CF_KEY_INTEGRATION_BRANCH}"
COMMAND_ANCESTOR: Final = "git merge-base --is-ancestor"


def _completed_implementation_run(
    store: Store, project_id: str, implementation: Node
) -> JournalEntry | None:
    """The implementation step's latest ``sq_run`` entry that ended ``completed``."""
    entries = store.journal_entries(project_id, node_id=implementation.id)
    for entry in reversed(entries):
        if entry.kind is not CommandKind.SQ_RUN:
            continue
        if (entry.result or {}).get(RESULT_OUTCOME) == RunOutcome.COMPLETED.value:
            return entry
    return None


@dataclass(frozen=True)
class PendingMerge:
    """A slice whose implementation is done and whose merge step is not."""

    slice_node: Node
    implementation: Node
    merge: Node
    index: int


def _pending_merges(tree: LifecycleTree) -> Sequence[PendingMerge]:
    """Each slice awaiting its merge."""
    pending: list[PendingMerge] = []
    for slice_node in tree.nodes:
        index = slice_node.cf.index
        if slice_node.kind is not NodeKind.SLICE or index is None:
            continue
        steps = {child.cf.phase: child for child in tree.children(slice_node)}
        implementation = steps.get(LifecycleStep.IMPLEMENTATION.value)
        merge = steps.get(LifecycleStep.MERGE.value)
        if (
            implementation is not None
            and merge is not None
            and implementation.status is NodeStatus.DONE
            and merge.status is not NodeStatus.DONE
        ):
            pending.append(PendingMerge(slice_node, implementation, merge, index))
    return pending


def _read_failed(node: Node, checkout: Path, command: str, reason: str) -> Fault:
    return Fault(
        FaultKind.CHECKOUT_READ_FAILED,
        f"{command} gave no usable answer in {checkout}: {reason}",
        node_id=node.id,
        extra={"checkout": str(checkout), "command": command, "reason": reason},
    )


@dataclass(frozen=True)
class _Observed:
    """A slice's merge observation, with the target it was read against."""

    state: MergeObservation
    target: str | None = None


def _observe_one(
    pending: PendingMerge,
    entry: JournalEntry | None,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> _Observed | Fault | None:
    """One slice's observation, a fault for a failed read, or ``None`` when cut off."""
    reason = unobservable_reason(entry, pending.index)
    if reason is not None:
        return _Observed(Unobservable(reason))
    if entry is None:
        return _Observed(Unobservable(REASON_NO_RUN))
    _, head = _recorded_git(entry)
    if head is None:
        return _Observed(Unobservable(REASON_NO_GIT))
    merge = pending.merge
    checkout = Path(text_parameter(entry, PARAM_CHECKOUT))
    project = pending.slice_node.cf.project
    if project is None:
        reason = f"slice {pending.slice_node.id} carries no CF project"
        return _read_failed(merge, checkout, COMMAND_TARGET, reason)
    target = read_target(checkout, project, budget, run, timeout_seconds)
    if target is None:
        return None
    if isinstance(target, ReadFailure):
        return _read_failed(merge, checkout, COMMAND_TARGET, target.detail)
    answer = git_read(
        is_ancestor_args(head, target), checkout, budget, run, timeout_seconds
    )
    if answer is None:
        return None
    if isinstance(answer, GitReadFailure):
        return _read_failed(merge, checkout, COMMAND_ANCESTOR, answer.detail)
    state = merge_state(entry, pending.index, answer.exit_code)
    if state is None:
        reason = f"exited {answer.exit_code}: {answer.stderr_head}"
        return _read_failed(merge, checkout, COMMAND_ANCESTOR, reason)
    return _Observed(state, target)


def observe_merges(
    store: Store,
    tree: LifecycleTree,
    project_id: str,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
    faults: TickFaults,
) -> MergePass:
    """Observe the merge of every slice whose implementation is done (D9).

    A ``merged`` observation completes the merge step in the same pass, so the view
    built after it sees the step done. A read that fails adds a project-scoped
    ``checkout_read_failed`` fault and gives that slice no observation; a pass the
    budget cuts off ends there and the next tick goes on.
    """
    has_open = {e.node_id for e in store.unresolved_journal_entries(project_id)}
    found: dict[str, MergeObservation] = {}
    wrote = False
    for pending in _pending_merges(tree):
        entry = _completed_implementation_run(store, project_id, pending.implementation)
        result = _observe_one(pending, entry, budget, run, timeout_seconds)
        if result is None:
            return MergePass(found, wrote, True)
        if isinstance(result, Fault):
            faults.add(result)
            continue
        found[pending.merge.id] = result.state
        if isinstance(result.state, Merged):
            detail = f"observed: {result.state.head} reachable from {result.target}"
            done = complete_step(
                store, pending.merge, LifecycleStep.MERGE, has_open, detail=detail
            )
            wrote = done or wrote
    return MergePass(found, wrote, False)
