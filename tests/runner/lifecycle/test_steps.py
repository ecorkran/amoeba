"""The step vocabulary, the step map, and the per-step completion predicates (D3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ast_strings import string_constants

from amoeba.runner.lifecycle import steps
from amoeba.runner.lifecycle.steps import (
    STEP_MAP,
    STEP_SEQUENCE,
    Executor,
    LifecycleStep,
    PlanObservation,
    StepLevel,
    StepSpec,
    step_complete,
    step_rank,
    steps_at,
)
from amoeba.upstream.context_forge import PlanEntryStatus, UnknownPlanStatus

SRC = Path(steps.__file__).parents[2]


def test_every_step_has_a_spec() -> None:
    assert set(STEP_MAP) == set(LifecycleStep)
    assert len(LifecycleStep) == 7


def test_step_sequence_holds_every_step_exactly_once() -> None:
    assert set(STEP_SEQUENCE) == set(LifecycleStep)
    assert len(STEP_SEQUENCE) == len(LifecycleStep)


def test_step_sequence_is_the_process_order() -> None:
    assert [step.value for step in STEP_SEQUENCE] == [
        "architecture",
        "slice_plan",
        "slice_design",
        "tasks",
        "implementation",
        "merge",
        "integration",
    ]


def test_step_rank_increases_along_the_sequence() -> None:
    ranks = [step_rank(step) for step in STEP_SEQUENCE]
    assert ranks == list(range(len(STEP_SEQUENCE)))


def test_the_pipeline_is_set_exactly_for_the_three_pipeline_steps() -> None:
    with_pipeline = {step for step, spec in STEP_MAP.items() if spec.pipeline}
    assert with_pipeline == {
        LifecycleStep.SLICE_DESIGN,
        LifecycleStep.TASKS,
        LifecycleStep.IMPLEMENTATION,
    }
    assert {STEP_MAP[step].pipeline for step in with_pipeline} == {"P4", "P5", "P6"}
    for step, spec in STEP_MAP.items():
        assert (spec.executor is Executor.PIPELINE) == (step in with_pipeline)


def test_the_map_is_read_only() -> None:
    with pytest.raises(TypeError):
        STEP_MAP[LifecycleStep.TASKS] = STEP_MAP[LifecycleStep.MERGE]  # type: ignore[index]


def test_a_pipeline_on_a_human_step_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot have a pipeline"):
        StepSpec(StepLevel.SLICE, Executor.HUMAN, "P4")


def test_a_pipeline_step_without_a_pipeline_is_refused() -> None:
    with pytest.raises(ValueError, match="needs a pipeline"):
        StepSpec(StepLevel.SLICE, Executor.PIPELINE)


def test_steps_at_returns_each_level_in_map_order() -> None:
    assert steps_at(StepLevel.INITIATIVE) == (
        LifecycleStep.ARCHITECTURE,
        LifecycleStep.SLICE_PLAN,
        LifecycleStep.INTEGRATION,
    )
    assert steps_at(StepLevel.SLICE) == (
        LifecycleStep.SLICE_DESIGN,
        LifecycleStep.TASKS,
        LifecycleStep.IMPLEMENTATION,
        LifecycleStep.MERGE,
    )


# -- completion ----------------------------------------------------------------

REPORTED_COMPLETE_STEPS = (
    LifecycleStep.SLICE_DESIGN,
    LifecycleStep.TASKS,
    LifecycleStep.IMPLEMENTATION,
    LifecycleStep.MERGE,
)


def test_architecture_needs_an_arch_file() -> None:
    step = LifecycleStep.ARCHITECTURE
    assert step_complete(step, PlanObservation(False, arch_file="120-arch.x.md"))
    assert not step_complete(step, PlanObservation(False, arch_file=None))
    assert not step_complete(step, PlanObservation(False, arch_file=""))


def test_slice_plan_needs_the_slice_list_read() -> None:
    step = LifecycleStep.SLICE_PLAN
    assert step_complete(step, PlanObservation(False, slice_list_read=True))
    assert not step_complete(step, PlanObservation(False, slice_list_read=False))


@pytest.mark.parametrize("step", REPORTED_COMPLETE_STEPS)
@pytest.mark.parametrize(
    ("status", "is_checked", "expected"),
    [
        (PlanEntryStatus.COMPLETE, False, True),
        (PlanEntryStatus.IN_PROGRESS, True, True),
        (None, True, True),
        (PlanEntryStatus.IN_PROGRESS, False, False),
        (PlanEntryStatus.NOT_STARTED, False, False),
        (UnknownPlanStatus("odd"), False, False),
        (None, False, False),
    ],
)
def test_slice_steps_complete_when_cf_reports_the_slice_complete(
    step: LifecycleStep,
    status: PlanEntryStatus | UnknownPlanStatus | None,
    is_checked: bool,
    expected: bool,
) -> None:
    assert step_complete(step, PlanObservation(is_checked, status)) is expected


def test_integration_follows_is_checked_and_not_status() -> None:
    step = LifecycleStep.INTEGRATION
    assert step_complete(step, PlanObservation(True, PlanEntryStatus.IN_PROGRESS))
    assert not step_complete(step, PlanObservation(False, PlanEntryStatus.COMPLETE))


# -- spelled once --------------------------------------------------------------


def test_no_other_runner_module_spells_a_step_value() -> None:
    values = {step.value for step in LifecycleStep}
    others = [
        p for p in sorted((SRC / "runner").rglob("*.py")) if p != Path(steps.__file__)
    ]
    assert others
    for path in others:
        clashes = values.intersection(string_constants(path))
        assert not clashes, f"{path.name} spells {sorted(clashes)}"
