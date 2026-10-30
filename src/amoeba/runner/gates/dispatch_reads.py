"""The reads before a launch or resume, and the check they feed (slice 128, D5).

For each candidate (``launch_candidates``) the Runner reads, under ``TickBudget`` and
in this order: ``git status`` and the target (``git.integration_branch``). CF's gate
is not read: the pipeline owns its gates (slice 132, D3). A read that cannot give a
usable answer is a :class:`DispatchReadFailed` and blocks nothing: the slice is not
at fault, and a retry costs only a read. ``None`` means the budget ran
out. :func:`check_candidate` combines the reads with the pure rules into a
:class:`DispatchCheck`, the evidence a launch's journal entry will record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.gates.candidates import Candidate
from amoeba.runner.gates.cf_reads import ReadFailure, read_target
from amoeba.runner.gates.predispatch import (
    DIRTY_PATHS_SHOWN,
    DispatchCheck,
    Ok,
    branch_rule,
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


@dataclass(frozen=True)
class DispatchReads:
    """What the reads found."""

    git: GitStatus
    target: str


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
    return DispatchReads(status, target)


def check_candidate(candidate: Candidate, reads: DispatchReads) -> DispatchCheck:
    """Apply the git rule to the reads: ``Block`` or ``Ok`` with its evidence (D5)."""
    block = branch_rule(
        reads.git, reads.target, candidate.slice_index, resume=candidate.resume
    )
    if block is not None:
        return block
    return Ok(_evidence(candidate, reads))


def _evidence(candidate: Candidate, reads: DispatchReads) -> dict[str, object]:
    """What the dispatch decision was based on, for the launch's journal entry."""
    evidence: dict[str, object] = {
        EVIDENCE_BRANCH: reads.git.branch,
        EVIDENCE_HEAD: reads.git.head,
        EVIDENCE_TARGET: reads.target,
    }
    if candidate.resume:
        evidence[EVIDENCE_DIRTY_PATHS] = list(reads.git.dirty[:DIRTY_PATHS_SHOWN])
        evidence[EVIDENCE_DIRTY_COUNT] = len(reads.git.dirty)
    return evidence
