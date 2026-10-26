"""The reads before a launch or resume, and the check they feed (slice 128, D5).

For each candidate (``launch_candidates``) the Runner reads, under ``TickBudget`` and
in this order: ``git status``, the target (``git.integration_branch``) and, for a
fresh or reissued ``tasks`` or ``implementation`` launch, CF's gate. A read that
cannot give a usable answer is a :class:`DispatchReadFailed` and blocks nothing: the
step is not at fault, and a retry costs only a read. ``None`` means the budget ran
out. :func:`check_candidate` combines the reads with the pure rules into a
:class:`DispatchCheck`, the evidence a launch's journal entry will record.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.gates.cf_reads import ReadFailure, read_gate, read_target
from amoeba.runner.gates.cf_status import CFActiveSlice, parse_status
from amoeba.runner.gates.predispatch import (
    DIRTY_PATHS_SHOWN,
    EVIDENCE_GATE_REVIEW_TYPE,
    EVIDENCE_GATE_STATUS,
    Block,
    Candidate,
    Disagreement,
    DispatchCheck,
    NoResult,
    Ok,
    branch_rule,
    entry_gate,
)
from amoeba.runner.git_read import (
    GitReadFailure,
    GitStatus,
    git_read,
    parse_porcelain_v2,
    status_args,
)
from amoeba.runner.lifecycle.plan_read import (
    CF_KEY_INTEGRATION_BRANCH,
    CF_STATUS_COMMAND,
)

#: ``Ok`` evidence keys that the gate half does not set (D5).
EVIDENCE_BRANCH: Final = "branch"
EVIDENCE_HEAD: Final = "head"
EVIDENCE_TARGET: Final = "target"
EVIDENCE_DIRTY_PATHS: Final = "dirty_paths"
EVIDENCE_DIRTY_COUNT: Final = "dirty_count"

#: The names a failed read gives for itself in a ``checkout_read_failed`` payload.
COMMAND_GIT_STATUS: Final = "git status"
COMMAND_CF_TARGET: Final = f"cf config get {CF_KEY_INTEGRATION_BRANCH}"
COMMAND_CF_STATUS: Final = "cf " + " ".join(CF_STATUS_COMMAND)


@dataclass(frozen=True)
class DispatchReads:
    """What the reads found. ``gate`` is ``None`` when no gate read was due."""

    git: GitStatus
    target: str
    gate: CFActiveSlice | None


@dataclass(frozen=True)
class DispatchReadFailed:
    """A read gave no usable answer: which command, and why."""

    command: str
    reason: str


def read_dispatch_facts(
    candidate: Candidate, budget: TickBudget, run: CfRun, timeout_seconds: float
) -> DispatchReads | DispatchReadFailed | None:
    """Take D5's reads for one candidate; ``None`` if the budget ran out."""
    checkout = candidate.checkout.path
    answer = git_read(status_args(), checkout, budget, run, timeout_seconds)
    if answer is None:
        return None
    if isinstance(answer, GitReadFailure):
        return DispatchReadFailed(COMMAND_GIT_STATUS, answer.detail)
    if answer.exit_code != 0:
        reason = f"exited {answer.exit_code}: {answer.stderr_head}"
        return DispatchReadFailed(COMMAND_GIT_STATUS, reason)
    status = parse_porcelain_v2(answer.stdout)
    target = read_target(
        checkout, candidate.cf_project_id, budget, run, timeout_seconds
    )
    if target is None:
        return None
    if isinstance(target, ReadFailure):
        return DispatchReadFailed(COMMAND_CF_TARGET, target.detail)
    if not candidate.needs_gate:
        return DispatchReads(status, target, None)
    return _with_gate(candidate, status, target, budget, run, timeout_seconds)


def _with_gate(
    candidate: Candidate,
    status: GitStatus,
    target: str,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> DispatchReads | DispatchReadFailed | None:
    document = read_gate(
        candidate.checkout.path,
        candidate.checkout.worktree_id,
        candidate.cf_project_id,
        budget,
        run,
        timeout_seconds,
    )
    if document is None:
        return None
    if isinstance(document, ReadFailure):
        return DispatchReadFailed(COMMAND_CF_STATUS, document.detail)
    active = parse_status(document)
    if active is None:
        return DispatchReadFailed(COMMAND_CF_STATUS, "no usable activeSlice")
    return DispatchReads(status, target, active)


def check_candidate(
    candidate: Candidate, reads: DispatchReads, *, accepted: bool
) -> DispatchCheck | Disagreement | None:
    """Combine the git rule and the entry gate; ``None`` is no result (D5).

    ``accepted`` says the PM accepted the candidate's predecessor in the store.
    """
    block = branch_rule(
        reads.git,
        reads.target,
        candidate.pipeline,
        candidate.slice_index,
        resume=candidate.resume,
    )
    if block is not None:
        return block
    if reads.gate is None:
        return Ok(_evidence(candidate, reads, {}))
    gate = entry_gate(
        candidate.step, reads.gate, candidate.slice_index, accepted=accepted
    )
    if isinstance(gate, NoResult):
        return None
    if isinstance(gate, Block):
        return gate
    if isinstance(gate, Disagreement):
        ok = Ok(_evidence(candidate, reads, gate.ok.evidence))
        return Disagreement(ok, gate.gate)
    return Ok(_evidence(candidate, reads, gate.evidence))


def _evidence(
    candidate: Candidate, reads: DispatchReads, gate_evidence: Mapping[str, object]
) -> dict[str, object]:
    """What the dispatch decision was based on, for the launch's journal entry."""
    evidence: dict[str, object] = {
        EVIDENCE_BRANCH: reads.git.branch,
        EVIDENCE_HEAD: reads.git.head,
        EVIDENCE_TARGET: reads.target,
        EVIDENCE_GATE_STATUS: None,
        EVIDENCE_GATE_REVIEW_TYPE: None,
        **gate_evidence,
    }
    if candidate.resume:
        evidence[EVIDENCE_DIRTY_PATHS] = list(reads.git.dirty[:DIRTY_PATHS_SHOWN])
        evidence[EVIDENCE_DIRTY_COUNT] = len(reads.git.dirty)
    return evidence
