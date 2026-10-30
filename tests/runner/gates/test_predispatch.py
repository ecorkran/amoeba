"""D5, D6 (slice 132, D3): the one branch rule, over every row of its table."""

from __future__ import annotations

import pytest

from amoeba.runner.faults import FaultKind
from amoeba.runner.gates.predispatch import (
    DIRTY_PATHS_SHOWN,
    Block,
    allowed_branches,
    branch_rule,
)
from amoeba.runner.git_read import GitStatus
from runner.gates.purity import io_use

TARGET = "main"
SLICE = 128
OWN = "128-slice.gates-git-and-human-steps"
HEAD = "abc123"


def _git(branch: str | None, *dirty: str) -> GitStatus:
    return GitStatus(branch=branch, head=HEAD, dirty=tuple(dirty))


def _rule(
    status: GitStatus, *, resume: bool = False, target: str = TARGET
) -> Block | None:
    return branch_rule(status, target, SLICE, resume=resume)


def test_a_clean_tree_on_the_target_is_allowed() -> None:
    assert _rule(_git("main")) is None


def test_dirty_tree_blocks_launch() -> None:
    block = _rule(_git("main", "a.txt", "b.txt"))

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_DIRTY
    assert block.payload == {"paths": ["a.txt", "b.txt"], "path_count": 2}


def test_only_the_first_twenty_dirty_paths_are_listed_but_all_are_counted() -> None:
    paths = tuple(f"f{i}.txt" for i in range(DIRTY_PATHS_SHOWN + 5))

    block = _rule(_git("main", *paths))

    assert block is not None
    assert block.payload["paths"] == list(paths[:DIRTY_PATHS_SHOWN])
    assert block.payload["path_count"] == DIRTY_PATHS_SHOWN + 5


def test_resume_not_blocked_by_its_own_dirty_tree() -> None:
    assert _rule(_git("main", "work.txt"), resume=True) is None
    assert _rule(_git(OWN, "work.txt"), resume=True) is None


def test_a_resume_is_still_checked_for_its_branch() -> None:
    block = _rule(_git("other-branch", "work.txt"), resume=True)

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH


def test_a_fresh_launch_is_refused_off_the_target_even_on_the_slice_branch() -> None:
    block = _rule(_git(OWN))

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH
    assert block.payload["branch"] == OWN
    assert block.payload["target"] == TARGET
    assert block.payload["allowed"] == (TARGET,)
    assert OWN in block.context and TARGET in block.context


def test_a_resume_is_allowed_on_this_slices_own_branch() -> None:
    assert _rule(_git(OWN), resume=True) is None


@pytest.mark.parametrize(
    "branch",
    ["129-slice.another-slice", "feature/x", "128-notslice", "dev/erik/128-slice.x"],
)
def test_a_resume_blocks_on_another_slices_branch_or_any_other(branch: str) -> None:
    block = _rule(_git(branch), resume=True)

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH
    assert block.payload["allowed"] == (TARGET, f"{SLICE}-slice.*")


def test_a_slash_prefixed_branch_is_not_the_slices_own() -> None:
    assert _rule(_git(f"dev/{OWN}"), resume=True) is not None


def test_detached_head_blocks() -> None:
    block = _rule(_git(None))

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH
    assert block.payload["branch"] is None


def test_an_integration_branch_as_target_blocks_main() -> None:
    block = _rule(_git("main"), target="dev/erik")

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH
    assert _rule(_git("dev/erik"), target="dev/erik") is None


def test_the_branch_comes_before_the_dirty_tree() -> None:
    block = _rule(_git("other", "a.txt"))

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH


def test_allowed_branches_by_launch_or_resume() -> None:
    assert allowed_branches("main", 7, resume=False) == ("main",)
    assert allowed_branches("main", 7, resume=True) == ("main", "7-slice.*")


def test_the_module_does_no_io() -> None:
    import amoeba.runner.gates.predispatch as module

    assert io_use(module) == []
