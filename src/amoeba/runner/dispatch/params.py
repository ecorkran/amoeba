"""The pipeline and parameters a step is launched with (D5), defined once.

The pipeline comes from ``STEP_MAP``. Every pipeline step gets the slice index. The
implementation step (``P6``) declares ``merge: "true"``, so its ``merge`` parameter
follows the project's merge policy (slice 128, D8): under ``human`` it gets
``merge=false`` ("merging is a human step by default"), under ``auto`` it gets none
and ``P6`` merges. Other parameters (models, revision limits) are not passed:
Squadron's pipeline defaults apply.

The journal keys that record the policy, the target branch and the pre-dispatch check
on a launch's entry are defined here too; they are evidence, not ``-p`` parameters.
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
from amoeba.runner.project_config import MergePolicy

#: The parameter keys and the one value ``merge`` takes when disabled. ``slice`` is
#: the pipeline's primary parameter, which ``build_argv`` passes as the target.
PARAM_SLICE: Final = TARGET_PARAM_KEY
PARAM_MERGE: Final = "merge"
MERGE_DISABLED: Final = "false"

#: Journal parameter keys a launch's entry records beside its ``-p`` params (D8, D5).
PARAM_MERGE_POLICY: Final = "merge_policy"
PARAM_TARGET: Final = "target"
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


def dispatch_params(
    step: LifecycleStep, slice_index: int, merge_policy: MergePolicy
) -> Mapping[str, str]:
    """The ``-p`` parameters for launching ``step``'s pipeline on a slice.

    Raises:
        ValueError: ``step`` is a human step.
    """
    pipeline_for(step)
    params = {PARAM_SLICE: str(slice_index)}
    if step is LifecycleStep.IMPLEMENTATION and merge_policy is MergePolicy.HUMAN:
        params[PARAM_MERGE] = MERGE_DISABLED
    return params
