"""Pre-dispatch checks: what a checkout must say before a launch (D5, D6; 132, D3).

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
from amoeba.runner.git_read import GitStatus
from amoeba.upstream.context_forge import parse_slice_stem

#: How many changed paths a ``checkout_dirty`` block lists; the count is always given.
DIRTY_PATHS_SHOWN: Final = 20

#: Block payload keys (D5, D11).
PAYLOAD_BRANCH: Final = "branch"
PAYLOAD_TARGET: Final = "target"
PAYLOAD_ALLOWED: Final = "allowed"
PAYLOAD_PATHS: Final = "paths"
PAYLOAD_PATH_COUNT: Final = "path_count"


@dataclass(frozen=True)
class Ok:
    """The checkout allows the dispatch; ``evidence`` says on what basis."""

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


def allowed_branches(target: str, slice_index: int, *, resume: bool) -> tuple[str, ...]:
    """The branches a dispatch may start on, for a message: the target, and for a
    resume this slice's own branch (any branch named ``{index}-slice.*``)."""
    if resume:
        return (target, f"{slice_index}-slice.*")
    return (target,)


def is_slice_branch(branch: str, slice_index: int) -> bool:
    """Whether ``branch`` is the slice's own branch: ``{index}-slice.*`` (D6).

    ``parse_slice_stem`` reads only the last path part, so a "/"-prefixed name is
    never the slice's own branch: Squadron names slice branches with no prefix.
    """
    stem = parse_slice_stem(branch)
    return stem is not None and "/" not in branch and stem.index == slice_index


def _is_allowed(branch: str, target: str, slice_index: int, *, resume: bool) -> bool:
    if branch == target:
        return True
    return resume and is_slice_branch(branch, slice_index)


def branch_rule(
    status: GitStatus,
    target: str,
    slice_index: int,
    *,
    resume: bool,
) -> Block | None:
    """The git half of the pre-dispatch check; the first rule that applies decides.

    1. A detached HEAD blocks. 2. A branch outside the allowed set blocks: a launch
    or reissue may start only on the target, a resume on the target or the slice's
    own branch (132, D3). 3. A launch or reissue with any changed, staged, unmerged
    or untracked path blocks; a resume never does, because a stopped run's tree may
    hold its own uncommitted work (D5).
    """
    allowed = allowed_branches(target, slice_index, resume=resume)
    if status.branch is None:
        return Block(
            FaultKind.CHECKOUT_BRANCH,
            "the checkout is on a detached HEAD, not on a branch",
            {PAYLOAD_BRANCH: None, PAYLOAD_TARGET: target, PAYLOAD_ALLOWED: allowed},
        )
    if not _is_allowed(status.branch, target, slice_index, resume=resume):
        return Block(
            FaultKind.CHECKOUT_BRANCH,
            f"the checkout is on {status.branch!r}; a dispatch may start only on "
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
