"""D5: the pipeline and parameters come from one place."""

from __future__ import annotations

from pathlib import Path

import pytest
from ast_strings import string_constants

import amoeba.runner as runner_package
from amoeba.runner.dispatch.params import (
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


@pytest.mark.parametrize(
    "step",
    [LifecycleStep.SLICE_DESIGN, LifecycleStep.TASKS, LifecycleStep.IMPLEMENTATION],
)
def test_every_pipeline_step_gets_only_the_slice(step: LifecycleStep) -> None:
    assert dispatch_params(step, 125) == {PARAM_SLICE: "125"}


@pytest.mark.parametrize(
    "step",
    [step for step, spec in STEP_MAP.items() if spec.executor is not Executor.PIPELINE],
)
def test_a_human_step_has_no_pipeline_or_params(step: LifecycleStep) -> None:
    with pytest.raises(ValueError, match="not run by a pipeline"):
        pipeline_for(step)
    with pytest.raises(ValueError, match="not run by a pipeline"):
        dispatch_params(step, 1)


def test_no_runner_module_passes_a_merge_parameter() -> None:
    """Whether a pipeline merges is the pipeline's business (slice 132, D2)."""
    spellers = {
        path.name
        for path in RUNNER_SRC.rglob("*.py")
        if "merge" in string_constants(path)
        and path not in {STEP_NAMES_FILE, PARAMS_FILE}
    }

    assert spellers == set()
