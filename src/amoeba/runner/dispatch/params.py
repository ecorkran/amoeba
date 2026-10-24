"""The pipeline and parameters a step is launched with (D5), defined once.

The pipeline comes from ``STEP_MAP``. Every pipeline step gets the slice index; the
implementation step (``P6``) also gets ``merge=false``, always, in this slice: ``P6``
declares ``merge: "true"``, and without the parameter its first production run would
merge, which breaks "merging is a human step by default". Slice 128 replaces the
fixed value with the per-project merge policy. Other parameters (models, revision
limits) are not passed: Squadron's pipeline defaults apply.
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

#: The parameter keys and the one value ``merge`` takes in this slice. ``slice`` is
#: the pipeline's primary parameter, which ``build_argv`` passes as the target.
PARAM_SLICE: Final = TARGET_PARAM_KEY
PARAM_MERGE: Final = "merge"
MERGE_DISABLED: Final = "false"


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
    params = {PARAM_SLICE: str(slice_index)}
    if step is LifecycleStep.IMPLEMENTATION:
        params[PARAM_MERGE] = MERGE_DISABLED
    return params
