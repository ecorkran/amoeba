"""The outcome observation: CF's gate, the design and git when a run completes (D2).

For every finished ``sq_run`` entry whose outcome is ``completed``,
:func:`observe_outcome` reads, in the entry's checkout and in this order: CF's gate,
the slice's design file path, the review gate's effective date, the design file, and
for ``implementation`` git's branch and head. A read that fails is recorded as
failed, never raised and never defaulted; only a tick-budget cut-off returns ``None``,
and the run is then observed again next tick. The two hatch checks (D4) are derived
from the same reads. The observation's value types and :func:`gate_state_at_exit`, the
routing input read from the stored gate record (D3), are in ``outcome_record.py``.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.gates.cf_reads import (
    ReadFailure,
    read_config,
    read_design_file,
    read_gate,
)
from amoeba.runner.gates.cf_status import (
    CFActiveSlice,
    parse_status,
    position_of,
)
from amoeba.runner.gates.hatches import (
    DesignMissing,
    DesignSource,
    DesignText,
    hatch_checks,
)
from amoeba.runner.gates.outcome_record import (
    GateRead,
    GitRead,
    OutcomeObservation,
    ReadFailed,
    unobservable,
)
from amoeba.runner.git_read import (
    GitReadFailure,
    git_read,
    parse_porcelain_v2,
    status_args,
)
from amoeba.runner.launch import text_parameter
from amoeba.runner.lifecycle.plan_read import CF_KEY_REVIEW_GATE_EFFECTIVE_DATE
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import PARAM_CHECKOUT, JournalEntry, Node


def observe_outcome(
    entry: JournalEntry,
    step: LifecycleStep,
    slice_node: Node,
    initiative_index: int,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
    amoeba_version: str,
) -> OutcomeObservation | None:
    """Take D2's reads for one completed entry, or ``None`` if the budget ran out.

    CF chooses a worktree by the working directory, so every read runs in the entry's
    checkout.

    A slice node with no CF project or index cannot be read, so it is observed as
    :func:`unobservable`.

    Raises:
        ValueError: The entry has no usable checkout.
    """
    checkout = Path(text_parameter(entry, PARAM_CHECKOUT))
    cf_project_id, slice_index = slice_node.cf.project, slice_node.cf.index
    if cf_project_id is None or slice_index is None:
        reason = f"slice node {slice_node.id} carries no CF project or index"
        return unobservable(entry, slice_node.id, reason, amoeba_version)
    gate = _gate(checkout, slice_index, cf_project_id, budget, run, timeout_seconds)
    design_file = read_design_file(
        initiative_index,
        slice_index,
        checkout,
        cf_project_id,
        budget,
        run,
        timeout_seconds,
    )
    effective = read_config(
        CF_KEY_REVIEW_GATE_EFFECTIVE_DATE,
        checkout,
        cf_project_id,
        budget,
        run,
        timeout_seconds,
    )
    if gate is None or design_file is None or effective is None:
        return None
    design = _design(checkout, design_file)
    git = None
    if step is LifecycleStep.IMPLEMENTATION:
        git = _git(checkout, budget, run, timeout_seconds)
        if git is None:
            return None
    return OutcomeObservation(
        gate=gate,
        design_path=design.path,
        design_failure=None if isinstance(design, DesignText) else design.reason,
        git=git,
        checks=hatch_checks(entry.id, slice_node.id, design, effective, amoeba_version),
    )


def _gate(
    checkout: Path,
    slice_index: int,
    cf_project_id: str,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> GateRead | ReadFailed | None:
    document = read_gate(checkout, None, cf_project_id, budget, run, timeout_seconds)
    if document is None:
        return None
    if isinstance(document, ReadFailure):
        return ReadFailed(document.detail)
    active = parse_status(document)
    if active is None or active.index is None:
        return ReadFailed("cf status has no usable activeSlice")
    if active.index != slice_index:
        return ReadFailed(
            f"cf status answered for slice {active.index}, not slice {slice_index}"
        )
    return _gate_read(active, active.index)


def _gate_read(active: CFActiveSlice, index: int) -> GateRead:
    info = active.gate_info
    return GateRead(
        index=index,
        status=active.status,
        review_type=None if info is None else info.review_type,
        position=position_of(active),
        rationale=None if info is None else info.rationale,
        pending_decisions=(
            None
            if active.pending_decisions is None
            else tuple(item.model_dump() for item in active.pending_decisions)
        ),
    )


def _design(checkout: Path, design_file: str | ReadFailure) -> DesignSource:
    """Read the design file, resolved against the checkout as review paths are."""
    if isinstance(design_file, ReadFailure):
        return DesignMissing(design_file.detail)
    path = (checkout / design_file).resolve()
    if not path.is_relative_to(checkout.resolve()):
        # CF named a path outside the checkout; it is not read.
        return DesignMissing("the design file is outside the checkout", design_file)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Specific: CF names a design the checkout does not hold. An answer.
        return DesignMissing("the design file is missing", design_file)
    except (OSError, UnicodeDecodeError) as error:
        # Specific: unreadable or not text. An answer, never a pass.
        return DesignMissing(f"the design file is unreadable: {error}", design_file)
    return DesignText(design_file, text)


def _git(
    checkout: Path, budget: TickBudget, run: CfRun, timeout_seconds: float
) -> GitRead | ReadFailed | None:
    answer = git_read(status_args(), checkout, budget, run, timeout_seconds)
    if answer is None:
        return None
    if isinstance(answer, GitReadFailure):
        return ReadFailed(answer.detail)
    if answer.exit_code != 0:
        return ReadFailed(f"git status exited {answer.exit_code}: {answer.stderr_head}")
    status = parse_porcelain_v2(answer.stdout)
    return GitRead(branch=status.branch, head=status.head)
