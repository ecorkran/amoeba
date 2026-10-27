"""The stored outcome observation: its value types, keys and the gate state (D2, D3).

Pure. :class:`OutcomeObservation` is what :func:`observe_outcome` (``outcome.py``)
reads when a run completes; ``to_result`` turns it into the entry result's
``outcome_observation`` and ``check_ids``. :func:`gate_state_at_exit` turns the stored
gate record into the routing input. Held apart from the reads so routing and ingestion
can import the record without the reads' imports.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from amoeba.runner.gates.cf_reads import ReadFailure
from amoeba.runner.gates.cf_status import EXIT_GATE, CFStatus, GatePosition
from amoeba.runner.gates.hatches import DesignMissing, hatch_checks
from amoeba.runner.ingest.record import RESULT_CHECK_IDS, RESULT_OUTCOME_OBSERVATION
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import CheckInput, JournalEntry

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
