"""D5: the pipeline and parameters come from one place."""

from __future__ import annotations

from pathlib import Path

import pytest
from ast_strings import string_constants

import amoeba.runner as runner_package
from amoeba.runner.dispatch.params import (
    MERGE_DISABLED,
    PARAM_MERGE,
    PARAM_SLICE,
    dispatch_params,
    pipeline_for,
)
from amoeba.runner.lifecycle.steps import (
    PIPELINE_P4,
    PIPELINE_P5,
    PIPELINE_P6,
    STEP_MAP,
    Executor,
    LifecycleStep,
)
from amoeba.runner.project_config import MergePolicy

RUNNER_SRC = Path(runner_package.__file__).parent
PARAMS_FILE = RUNNER_SRC / "dispatch" / "params.py"
#: ``steps.py`` spells "merge" as a lifecycle step's name, a different thing.
STEP_NAMES_FILE = RUNNER_SRC / "lifecycle" / "steps.py"


@pytest.mark.parametrize(
    ("step", "pipeline"),
    [
        (LifecycleStep.SLICE_DESIGN, PIPELINE_P4),
        (LifecycleStep.TASKS, PIPELINE_P5),
        (LifecycleStep.IMPLEMENTATION, PIPELINE_P6),
    ],
)
def test_each_pipeline_step_runs_its_pipeline(
    step: LifecycleStep, pipeline: str
) -> None:
    assert pipeline_for(step) == pipeline


def test_design_and_tasks_get_only_the_slice() -> None:
    assert dispatch_params(LifecycleStep.SLICE_DESIGN, 125, MergePolicy.HUMAN) == {
        PARAM_SLICE: "125"
    }
    assert dispatch_params(LifecycleStep.TASKS, 7, MergePolicy.HUMAN) == {
        PARAM_SLICE: "7"
    }


def test_implementation_also_gets_merge_false() -> None:
    assert dispatch_params(LifecycleStep.IMPLEMENTATION, 125, MergePolicy.HUMAN) == {
        PARAM_SLICE: "125",
        PARAM_MERGE: MERGE_DISABLED,
    }
    assert MERGE_DISABLED == "false"


@pytest.mark.parametrize("step", [LifecycleStep.SLICE_DESIGN, LifecycleStep.TASKS])
def test_a_planning_step_gets_only_the_slice_under_either_policy(
    step: LifecycleStep,
) -> None:
    for policy in MergePolicy:
        assert dispatch_params(step, 3, policy) == {PARAM_SLICE: "3"}


def test_auto_policy_gives_implementation_no_merge_param() -> None:
    assert dispatch_params(LifecycleStep.IMPLEMENTATION, 125, MergePolicy.AUTO) == {
        PARAM_SLICE: "125"
    }


@pytest.mark.parametrize(
    "step",
    [step for step, spec in STEP_MAP.items() if spec.executor is not Executor.PIPELINE],
)
def test_a_human_step_has_no_pipeline_or_params(step: LifecycleStep) -> None:
    with pytest.raises(ValueError, match="not run by a pipeline"):
        pipeline_for(step)
    with pytest.raises(ValueError, match="not run by a pipeline"):
        dispatch_params(step, 1, MergePolicy.HUMAN)


def test_merge_param_is_built_only_by_dispatch_params() -> None:
    spellers = {
        path
        for path in RUNNER_SRC.rglob("*.py")
        if PARAM_MERGE in string_constants(path) and path != STEP_NAMES_FILE
    }

    assert spellers == {PARAMS_FILE}
