"""The v1 lifecycle steps, who runs each, and when CF says each is complete (D3).

``STEP_MAP`` is the one place steps are defined. A step's value is the ``step`` text
in the store's ``attempt_counts`` and ``desired_states.drive_until_step`` columns,
which the store holds opaquely.

``merge`` is complete in v1 only when CF reports the slice complete; slice 128 adds
git observation. There are no gate steps: CF's review gate is a dispatch check.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from amoeba.upstream.context_forge import PlanStatus, reported_complete


class LifecycleStep(StrEnum):
    """The steps of one initiative's lifecycle, in map order."""

    ARCHITECTURE = "architecture"
    SLICE_PLAN = "slice_plan"
    SLICE_DESIGN = "slice_design"
    TASKS = "tasks"
    IMPLEMENTATION = "implementation"
    MERGE = "merge"
    INTEGRATION = "integration"


class StepLevel(StrEnum):
    """Whether a step belongs to an initiative or to one of its slices."""

    INITIATIVE = "initiative"
    SLICE = "slice"


class Executor(StrEnum):
    """Who does a step: a pipeline run, or a person."""

    PIPELINE = "pipeline"
    HUMAN = "human"


#: The pipelines that run steps.
PIPELINE_P4: Final = "P4"
PIPELINE_P5: Final = "P5"
PIPELINE_P6: Final = "P6"


@dataclass(frozen=True)
class StepSpec:
    """One step's level and executor; ``pipeline`` is set only for a pipeline step."""

    level: StepLevel
    executor: Executor
    pipeline: str | None = None

    def __post_init__(self) -> None:
        if self.executor is Executor.PIPELINE and self.pipeline is None:
            raise ValueError("a pipeline step needs a pipeline (got None)")
        if self.executor is not Executor.PIPELINE and self.pipeline is not None:
            raise ValueError(
                f"a {self.executor.value} step cannot have a pipeline "
                f"(got {self.pipeline!r})"
            )


STEP_MAP: Final[Mapping[LifecycleStep, StepSpec]] = MappingProxyType(
    {
        LifecycleStep.ARCHITECTURE: StepSpec(StepLevel.INITIATIVE, Executor.HUMAN),
        LifecycleStep.SLICE_PLAN: StepSpec(StepLevel.INITIATIVE, Executor.HUMAN),
        LifecycleStep.SLICE_DESIGN: StepSpec(
            StepLevel.SLICE, Executor.PIPELINE, PIPELINE_P4
        ),
        LifecycleStep.TASKS: StepSpec(StepLevel.SLICE, Executor.PIPELINE, PIPELINE_P5),
        LifecycleStep.IMPLEMENTATION: StepSpec(
            StepLevel.SLICE, Executor.PIPELINE, PIPELINE_P6
        ),
        LifecycleStep.MERGE: StepSpec(StepLevel.SLICE, Executor.HUMAN),
        LifecycleStep.INTEGRATION: StepSpec(StepLevel.INITIATIVE, Executor.HUMAN),
    }
)


def steps_at(level: StepLevel) -> tuple[LifecycleStep, ...]:
    """The steps of one level, in map order."""
    return tuple(step for step, spec in STEP_MAP.items() if spec.level is level)


@dataclass(frozen=True)
class PlanObservation:
    """What the plan read says about one initiative or slice.

    Attributes:
        is_checked: CF's ``isChecked`` for the entry.
        status: CF's status, or ``None`` when CF reported none.
        arch_file: The initiative's ``archFile``; ``None`` for a slice or none set.
        slice_list_read: Whether the initiative's slice list was read successfully.
    """

    is_checked: bool
    status: PlanStatus | None = None
    arch_file: str | None = None
    slice_list_read: bool = False


def step_complete(step: LifecycleStep, observation: PlanObservation) -> bool:
    """Whether the plan read shows ``step`` complete. One rule per step (D3)."""
    match step:
        case LifecycleStep.ARCHITECTURE:
            return bool(observation.arch_file)
        case LifecycleStep.SLICE_PLAN:
            return observation.slice_list_read
        case (
            LifecycleStep.SLICE_DESIGN
            | LifecycleStep.TASKS
            | LifecycleStep.IMPLEMENTATION
            | LifecycleStep.MERGE
        ):
            return reported_complete(observation)
        case LifecycleStep.INTEGRATION:
            # CF's checkbox, not its status: an initiative CF calls complete is
            # not integrated until the PM checks it.
            return observation.is_checked
