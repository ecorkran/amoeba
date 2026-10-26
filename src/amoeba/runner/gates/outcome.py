"""The outcome observation: CF's gate, the design and git when a run completes (D2).

For every finished ``sq_run`` entry whose outcome is ``completed``,
:func:`observe_outcome` reads, in the entry's checkout and in this order: CF's gate,
the slice's design file path, the review gate's effective date, the design file, and
for ``implementation`` git's branch and head. A read that fails is recorded as
failed, never raised and never defaulted; only a tick-budget cut-off returns ``None``,
and the run is then observed again next tick. The two hatch checks (D4) are derived
from the same reads. :func:`gate_state_at_exit` turns the stored gate record into the
routing input (D3).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.gates.cf_reads import (
    ReadFailure,
    read_config,
    read_design_file,
    read_gate,
)
from amoeba.runner.gates.cf_status import (
    EXIT_GATE,
    CFActiveSlice,
    CFStatus,
    GatePosition,
    parse_status,
    position_of,
)
from amoeba.runner.gates.hatches import (
    DesignMissing,
    DesignSource,
    DesignText,
    hatch_checks,
)
from amoeba.runner.git_read import (
    GitReadFailure,
    git_read,
    parse_porcelain_v2,
    status_args,
)
from amoeba.runner.ingest.record import RESULT_CHECK_IDS, RESULT_OUTCOME_OBSERVATION
from amoeba.runner.launch import text_parameter
from amoeba.runner.lifecycle.plan_read import CF_KEY_REVIEW_GATE_EFFECTIVE_DATE
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import PARAM_CHECKOUT, CheckInput, JournalEntry, Node

#: Keys of the stored observation (the "Entry result" shape in the LLD).
OBS_GATE: Final = "gate"
OBS_DESIGN_PATH: Final = "design_path"
OBS_DESIGN_FAILURE: Final = "design_failure"
OBS_GIT: Final = "git"
GATE_INDEX: Final = "index"
GATE_STATUS: Final = "status"
GATE_REVIEW_TYPE: Final = "review_type"
GATE_POSITION: Final = "position"
GATE_RATIONALE: Final = "rationale"
GATE_PENDING_DECISIONS: Final = "pending_decisions"
FAILURE: Final = "failure"
GIT_BRANCH: Final = "branch"
GIT_HEAD: Final = "head"

#: The gate_state values (D3), besides ``none``, which only the reducer produces.
GATE_CLEAR: Final = "clear"
GATE_PENDING_REVIEW: Final = "pending_review"
GATE_REVIEW_FAILED: Final = "review_failed"
GATE_PENDING_DECISION: Final = "pending_decision"
GATE_MISPLACED: Final = "misplaced"
GATE_UNKNOWN: Final = "unknown"


@dataclass(frozen=True)
class ReadFailed:
    """A read in the observation failed; ``reason`` names the command and why."""

    reason: str


@dataclass(frozen=True)
class GateRead:
    """CF's gate as it stood: the mapped position and the evidence CF gave."""

    index: int
    status: str
    review_type: str | None
    position: GatePosition
    rationale: str | None
    pending_decisions: tuple[Mapping[str, object], ...] | None


@dataclass(frozen=True)
class GitRead:
    """The checkout's branch (``None`` when detached) and head."""

    branch: str | None
    head: str | None


@dataclass(frozen=True)
class OutcomeObservation:
    """Everything read when a run completed, ready to store and to record."""

    gate: GateRead | ReadFailed
    design_path: str | None
    design_failure: str | None
    git: GitRead | ReadFailed | None
    checks: tuple[CheckInput, CheckInput]

    def to_result(self) -> dict[str, object]:
        """The two entry-result keys: the observation and the hatch check ids."""
        observation: dict[str, object] = {
            OBS_GATE: _gate_record(self.gate),
            OBS_DESIGN_PATH: self.design_path,
            OBS_DESIGN_FAILURE: self.design_failure,
        }
        if self.git is not None:
            observation[OBS_GIT] = _git_record(self.git)
        return {
            RESULT_OUTCOME_OBSERVATION: observation,
            RESULT_CHECK_IDS: [check.id for check in self.checks],
        }


def unobservable(
    entry: JournalEntry, node_id: str, reason: str, amoeba_version: str
) -> OutcomeObservation:
    """An observation for a run whose slice cannot be read at all.

    Every read is recorded as failed for ``reason``, and both hatch checks follow
    from that: the routing table escalates it, so nothing advances on it.
    """
    return OutcomeObservation(
        gate=ReadFailed(reason),
        design_path=None,
        design_failure=reason,
        git=None,
        checks=hatch_checks(
            entry.id,
            node_id,
            DesignMissing(reason),
            ReadFailure(reason),
            amoeba_version,
        ),
    )


def _gate_record(gate: GateRead | ReadFailed) -> dict[str, object]:
    if isinstance(gate, ReadFailed):
        return {FAILURE: gate.reason}
    return {
        GATE_INDEX: gate.index,
        GATE_STATUS: gate.status,
        GATE_REVIEW_TYPE: gate.review_type,
        GATE_POSITION: gate.position.name,
        GATE_RATIONALE: gate.rationale,
        GATE_PENDING_DECISIONS: (
            None if gate.pending_decisions is None else list(gate.pending_decisions)
        ),
    }


def _git_record(git: GitRead | ReadFailed) -> dict[str, object]:
    if isinstance(git, ReadFailed):
        return {FAILURE: git.reason}
    return {GIT_BRANCH: git.branch, GIT_HEAD: git.head}


def gate_state_at_exit(
    step: LifecycleStep, gate_record: Mapping[str, object] | None
) -> str:
    """The routing input ``gate_state`` for a completed ``step`` (D3).

    ``gate_record`` is the stored ``outcome_observation.gate``, or ``None`` for an
    entry ingested before this slice. A failed read and an unknown position are
    ``unknown``; a position one past the step's exit gate is ``clear``; any other is
    ``misplaced``: CF is not where this step leaves the slice.

    Raises:
        ValueError: ``step`` has no exit gate.
    """
    exit_gate = EXIT_GATE.get(step)
    if exit_gate is None:
        raise ValueError(f"step {step.value} has no exit gate")
    position = _stored_position(gate_record)
    if position is None or position is GatePosition.UNKNOWN:
        return GATE_UNKNOWN
    if position is GatePosition.PENDING_DECISION:
        return GATE_PENDING_DECISION
    if position is exit_gate:
        return _blocked_state(gate_record)
    if position is GatePosition(exit_gate + 1):
        return GATE_CLEAR
    return GATE_MISPLACED


def _stored_position(gate_record: Mapping[str, object] | None) -> GatePosition | None:
    if gate_record is None:
        return None
    name = gate_record.get(GATE_POSITION)
    if not isinstance(name, str) or name not in GatePosition.__members__:
        return None
    return GatePosition[name]


def _blocked_state(gate_record: Mapping[str, object] | None) -> str:
    """At the exit gate CF says which way it blocks, by its status text."""
    status = None if gate_record is None else gate_record.get(GATE_STATUS)
    text = status.strip().lower() if isinstance(status, str) else None
    if text == CFStatus.PENDING_REVIEW:
        return GATE_PENDING_REVIEW
    if text == CFStatus.REVIEW_FAILED:
        return GATE_REVIEW_FAILED
    return GATE_UNKNOWN


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
    try:
        text = (checkout / design_file).read_text(encoding="utf-8")
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
