"""The pipeline and parameters a step is launched with (D5), defined once.

The pipeline comes from ``STEP_MAP``. Every pipeline step gets the slice index and
nothing else: whether a pipeline merges is the pipeline's own business (slice 132, D2).
Other parameters (models, revision limits) are not passed: Squadron's pipeline
defaults apply.

The journal key that records the pre-dispatch check on a launch's entry is defined
here too; it is evidence, not a ``-p`` parameter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from amoeba.runner.launch import TARGET_PARAM_KEY
from amoeba.runner.lifecycle.steps import (
    STEP_MAP,
    Executor,
    LifecycleStep,
)

#: ``slice`` is the pipeline's primary parameter, which ``build_argv`` passes as the
#: target.
PARAM_SLICE: Final = TARGET_PARAM_KEY

#: The journal parameter key a launch's entry records beside its ``-p`` params (D5).
#: ``PARAM_MERGE_POLICY`` is read only by the unused merge module (Task 10.2b).
PARAM_MERGE_POLICY: Final = "merge_policy"
PARAM_DISPATCH_CHECK: Final = "dispatch_check"


def pipeline_for(step: LifecycleStep) -> str:
    """The pipeline that runs ``step``.

    Raises:
        ValueError: ``step`` is a human step, which no pipeline runs.
    """
    spec = STEP_MAP[step]
    if spec.executor is not Executor.PIPELINE or spec.pipeline is None:
        raise ValueError(f"step {step.value} is not run by a pipeline")
    return spec.pipeline


def dispatch_params(step: LifecycleStep, slice_index: int) -> Mapping[str, str]:
    """The ``-p`` parameters for launching ``step``'s pipeline on a slice.

    Raises:
        ValueError: ``step`` is a human step.
    """
    pipeline_for(step)
    return {PARAM_SLICE: str(slice_index)}
