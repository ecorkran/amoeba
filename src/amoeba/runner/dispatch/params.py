"""The parameters a slice is launched with, defined once (D2, slice 132).

The pipeline is the project's configured one and every launch gets the slice index
plus the project's own ``params``: whether a pipeline merges, or which models it
uses, is the pipeline's business. Config validation refuses a ``slice`` key in
``params``, so the slice index cannot be overridden here.

The journal key that records the pre-dispatch check on a launch's entry is defined
here too; it is evidence, not a ``-p`` parameter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from amoeba.runner.launch import TARGET_PARAM_KEY
from amoeba.runner.project_config import ProjectSettings

#: ``slice`` is the pipeline's primary parameter, which ``build_argv`` passes as the
#: target.
PARAM_SLICE: Final = TARGET_PARAM_KEY

#: The journal parameter key a launch's entry records beside its ``-p`` params (D5).
PARAM_DISPATCH_CHECK: Final = "dispatch_check"


def launch_params(settings: ProjectSettings, slice_index: int) -> Mapping[str, str]:
    """The ``-p`` parameters for launching the project's pipeline on a slice."""
    return {PARAM_SLICE: str(slice_index), **settings.params}
