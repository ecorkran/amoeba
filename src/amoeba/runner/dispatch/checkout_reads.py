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

import json
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final, cast

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import (
    OUTPUT_HEAD_CHARS,
    CfCallFailed,
    CfRun,
    output_head,
    run_cf,
)
from amoeba.runner.dispatch.candidates import Candidate
from amoeba.runner.dispatch.checkout_check import (
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
    cf_argv,
    config_get_command,
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


#: The target when ``git.integration_branch`` is empty: the key's own description says
#: "Empty means no integration branch — work branches fork from and merge into main".
DEFAULT_TARGET_BRANCH: Final = "main"

_VALUE_KEY: Final = "value"


@dataclass(frozen=True)
class ReadFailure:
    """A CF read gave no usable answer; ``detail`` names the command and why."""

    detail: str


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


def read_config(
    key: str,
    checkout: Path,
    cf_project_id: str,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> str | ReadFailure | None:
    """The string value of one CF config key as the checkout sees it.

    Runs in the checkout, because CF chooses a worktree by working directory. A
    read that cannot give a string ``value`` is a failure, never a default; the
    key's absence is not an empty value. ``None`` means the budget refused the call.
    """
    if not budget.allows_call():
        return None
    argv = cf_argv(config_get_command(key), cf_project_id)
    shown = " ".join(argv)
    completed = run_cf(argv, partial(run, cwd=checkout), timeout_seconds)
    if isinstance(completed, CfCallFailed):
        return ReadFailure(completed.detail)
    if completed.returncode != 0:
        head = output_head(completed)
        return ReadFailure(f"`{shown}` exited {completed.returncode}: {head}")
    head = completed.stdout[:OUTPUT_HEAD_CHARS]
    try:
        document: object = json.loads(completed.stdout)
    except json.JSONDecodeError:
        # Expected: CF printed something else. Reported, never guessed at.
        return ReadFailure(f"`{shown}` printed no JSON: {head!r}")
    if not isinstance(document, dict):
        return ReadFailure(f"`{shown}` did not print a JSON object: {head!r}")
    value = cast("dict[str, object]", document).get(_VALUE_KEY)
    if not isinstance(value, str):
        return ReadFailure(f"`{shown}` answered without a string value")
    return value


def read_target(
    checkout: Path,
    cf_project_id: str,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> str | ReadFailure | None:
    """The target branch: ``git.integration_branch``, or the default when empty."""
    value = read_config(
        CF_KEY_INTEGRATION_BRANCH,
        checkout,
        cf_project_id,
        budget,
        run,
        timeout_seconds,
    )
    if isinstance(value, str) and value.strip() == "":
        return DEFAULT_TARGET_BRANCH
    return value


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
