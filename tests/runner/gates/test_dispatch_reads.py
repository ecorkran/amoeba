"""D5: which steps are candidates, what is read for them, and the evidence kept."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from cf_stub import write_cf_stub
from cf_stub_gates import CONFIG_MODE_ENV, STATUS_MODE_ENV, GateMode

from amoeba.runner.budget import TickBudget
from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.faults import FaultKind
from amoeba.runner.gates.candidates import Candidate, launch_candidates
from amoeba.runner.gates.dispatch_reads import (
    DispatchReadFailed,
    DispatchReads,
    check_candidate,
    read_dispatch_facts,
)
from amoeba.runner.gates.predispatch import Block, Ok
from amoeba.runner.lifecycle.plan_read import CF_KEY_INTEGRATION_BRANCH
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import CommandKind, JournalEntry, JournalOutcome, JournalResolver
from runner.dispatch.dispatch_support import FIRST, SECOND, entry, facts, node
from runner.dispatch.pointer_support import budget_allowing, generous_budget
from runner.gate_rig import (
    config_knobs,
    git_checkout,
    single_status_knobs,
    status_fixture,
)
from runner.git_repo import commit_file, head_of, make_branch

TIMEOUT = 20.0
SLICE = 125
OWN = "125-slice.some-slice"


def _never_started() -> JournalEntry:
    return entry(
        CommandKind.SQ_RUN,
        "a",
        FIRST,
        JournalOutcome.NOT_APPLIED,
        resolved_by=JournalResolver.RECOVERY,
    )


# -- launch_candidates ---------------------------------------------------------


def _candidates(
    state: DispatchState,
    holders: dict[Path, frozenset[str]] | None = None,
    **kw: object,
) -> tuple[Candidate, ...]:
    entry_kwargs: dict[str, object] = {}
    if state is DispatchState.REISSUE:
        entry_kwargs["reissue_of"] = _never_started()
    if state in (DispatchState.RESUME, DispatchState.AUTO_RESUME):
        entry_kwargs["continues"] = entry(CommandKind.SQ_RUN, "a", FIRST)
    step_facts = facts(state, FIRST, **entry_kwargs, **kw)  # type: ignore[arg-type]
    return launch_candidates([node("a")], {"a": step_facts}, holders or {})


def test_a_ready_step_is_a_candidate_in_a_free_checkout() -> None:
    [candidate] = _candidates(DispatchState.READY)

    assert candidate.pipeline == "P5"
    assert candidate.resume is False


def test_a_ready_step_in_a_held_checkout_is_not_a_candidate() -> None:
    assert _candidates(DispatchState.READY, {FIRST: frozenset({"other"})}) == ()


def test_a_reissue_in_a_free_checkout_is_a_candidate_with_its_old_pipeline() -> None:
    [candidate] = _candidates(DispatchState.REISSUE)

    assert candidate.pipeline == "P5"


def test_a_reissue_in_a_held_checkout_is_not_a_candidate() -> None:
    assert _candidates(DispatchState.REISSUE, {FIRST: frozenset({"other"})}) == ()


@pytest.mark.parametrize(
    ("holders", "expected"),
    [
        ({}, 1),
        ({FIRST: frozenset({"a"})}, 1),
        ({FIRST: frozenset({"other"})}, 0),
        ({FIRST: frozenset({"a", "other"})}, 0),
        ({SECOND: frozenset({"other"})}, 1),
    ],
)
@pytest.mark.parametrize("state", [DispatchState.RESUME, DispatchState.AUTO_RESUME])
def test_a_resume_is_a_candidate_only_when_held_by_no_one_or_itself(
    state: DispatchState, holders: dict[Path, frozenset[str]], expected: int
) -> None:
    assert len(_candidates(state, holders)) == expected


@pytest.mark.parametrize("state", [DispatchState.RESUME, DispatchState.AUTO_RESUME])
def test_a_resume_continues_a_run(state: DispatchState) -> None:
    [candidate] = _candidates(state)

    assert candidate.resume is True


@pytest.mark.parametrize(
    "state",
    [DispatchState.IN_FLIGHT],
)
def test_other_states_are_never_candidates(state: DispatchState) -> None:
    assert _candidates(state) == ()


def test_a_step_with_no_facts_or_no_checkout_is_skipped() -> None:
    assert launch_candidates([node("a")], {}, {}) == ()
    unresolved = facts(DispatchState.READY, None)
    assert launch_candidates([node("a")], {"a": unresolved}, {}) == ()


# -- read_dispatch_facts -------------------------------------------------------


class World:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.checkout = git_checkout(tmp_path / "checkout")
        bin_dir = write_cf_stub(tmp_path / "bin")
        monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
        self.status("in_implementation_no_task_done")
        self.config({})

    def status(self, captured: str, index: int = SLICE) -> None:
        fixture = status_fixture(self.tmp_path / "s.json", captured, index)
        for name, value in single_status_knobs(fixture).items():
            self.monkeypatch.setenv(name, value)

    def config(self, values: dict[str, str]) -> None:
        for name, value in config_knobs(self.tmp_path, values).items():
            self.monkeypatch.setenv(name, value)

    def candidate(
        self,
        step: LifecycleStep = LifecycleStep.IMPLEMENTATION,
        *,
        resume: bool = False,
        automatic: bool = False,
    ) -> Candidate:
        state = DispatchState.AUTO_RESUME if automatic else DispatchState.RESUME
        return Candidate(
            "a",
            step,
            state if resume or automatic else DispatchState.READY,
            Checkout(self.checkout, None),
            "P6",
            SLICE,
            "cf-a",
        )

    def read(
        self, candidate: Candidate, budget: TickBudget | None = None
    ) -> DispatchReads | DispatchReadFailed | None:
        return read_dispatch_facts(
            candidate, budget or generous_budget(), subprocess.run, TIMEOUT
        )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return World(tmp_path, monkeypatch)


def test_the_reads_give_git_and_the_target(world: World) -> None:
    reads = world.read(world.candidate())

    assert isinstance(reads, DispatchReads)
    assert reads.git.branch == "main" and reads.git.head == head_of(world.checkout)
    assert reads.target == "main"


def test_the_target_is_the_integration_branch_when_one_is_set(world: World) -> None:
    world.config({CF_KEY_INTEGRATION_BRANCH: "dev/erik"})

    reads = world.read(world.candidate())

    assert isinstance(reads, DispatchReads) and reads.target == "dev/erik"


def test_cf_s_gate_is_not_read(world: World) -> None:
    """A failing ``cf status`` changes nothing: the pipeline owns its gates (132)."""
    world.monkeypatch.setenv(STATUS_MODE_ENV, GateMode.FAIL.value)

    result = world.read(world.candidate())

    assert isinstance(result, DispatchReads)


def test_a_failed_target_read_is_a_read_failure(world: World) -> None:
    world.monkeypatch.setenv(CONFIG_MODE_ENV, GateMode.FAIL.value)

    result = world.read(world.candidate())

    assert isinstance(result, DispatchReadFailed)
    assert CF_KEY_INTEGRATION_BRANCH in result.command


def test_a_checkout_that_is_not_a_repository_is_a_read_failure(world: World) -> None:
    world.monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(world.tmp_path))
    bare = world.tmp_path / "bare"
    bare.mkdir()
    candidate = world.candidate()
    candidate = Candidate(
        candidate.node_id,
        candidate.step,
        candidate.state,
        Checkout(bare, None),
        candidate.pipeline,
        candidate.slice_index,
        candidate.cf_project_id,
    )

    result = world.read(candidate)

    assert isinstance(result, DispatchReadFailed) and result.command == "git status"


def test_a_cut_off_at_any_read_returns_none(world: World) -> None:
    for calls in range(2):
        assert world.read(world.candidate(), budget_allowing(calls)) is None


# -- check_candidate -----------------------------------------------------------


def _reads(world: World, *, dirty: bool = False, branch: str = "main") -> DispatchReads:
    if branch != "main":
        make_branch(world.checkout, branch)
        commit_file(world.checkout, "x.txt", "x\n", "x")
    if dirty:
        (world.checkout / "work.txt").write_text("w\n")
    reads = world.read(world.candidate())
    assert isinstance(reads, DispatchReads)
    return reads


def test_the_evidence_for_a_launch_names_branch_head_and_target(
    world: World,
) -> None:
    reads = _reads(world)

    result = check_candidate(world.candidate(), reads)

    assert isinstance(result, Ok)
    assert result.evidence == {
        "branch": "main",
        "head": head_of(world.checkout),
        "target": "main",
    }


@pytest.mark.parametrize("automatic", [False, True])
def test_a_resume_s_evidence_names_its_dirty_paths_and_it_launches(
    world: World, automatic: bool
) -> None:
    (world.checkout / "work.txt").write_text("w\n")
    candidate = world.candidate(resume=not automatic, automatic=automatic)
    reads = world.read(candidate)
    assert isinstance(reads, DispatchReads)

    result = check_candidate(candidate, reads)

    assert isinstance(result, Ok)
    assert result.evidence["dirty_paths"] == ["work.txt"]
    assert result.evidence["dirty_count"] == 1


def test_a_dirty_tree_blocks_a_launch(world: World) -> None:
    reads = _reads(world, dirty=True)

    result = check_candidate(world.candidate(), reads)

    assert isinstance(result, Block) and result.fault_kind is FaultKind.CHECKOUT_DIRTY


def test_a_fresh_launch_on_the_slice_branch_blocks(world: World) -> None:
    reads = _reads(world, branch=OWN)

    result = check_candidate(world.candidate(), reads)

    assert isinstance(result, Block) and result.fault_kind is FaultKind.CHECKOUT_BRANCH


def test_a_resume_on_the_slice_branch_with_a_dirty_tree_passes(world: World) -> None:
    make_branch(world.checkout, OWN)
    commit_file(world.checkout, "x.txt", "x\n", "x")
    (world.checkout / "work.txt").write_text("w\n")
    candidate = world.candidate(resume=True)
    reads = world.read(candidate)
    assert isinstance(reads, DispatchReads)

    assert isinstance(check_candidate(candidate, reads), Ok)
