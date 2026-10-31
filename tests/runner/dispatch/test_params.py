"""D2 (slice 132): the parameters a slice is launched with come from one place."""

from __future__ import annotations

from pathlib import Path

from ast_strings import string_constants

import amoeba.runner as runner_package
from amoeba.runner.dispatch.params import PARAM_SLICE, launch_params
from amoeba.runner.project_config import ProjectSettings

RUNNER_SRC = Path(runner_package.__file__).parent


def test_a_launch_gets_the_slice_and_nothing_else_by_default() -> None:
    assert launch_params(ProjectSettings(pipeline="p456"), 125) == {PARAM_SLICE: "125"}


def test_the_projects_params_follow_the_slice_verbatim() -> None:
    settings = ProjectSettings(pipeline="p456", params={"model": "opus", "n": "2"})

    assert launch_params(settings, 7) == {PARAM_SLICE: "7", "model": "opus", "n": "2"}


def test_no_runner_module_passes_a_merge_parameter() -> None:
    """Whether a pipeline merges is the pipeline's business (slice 132, D2)."""
    spellers = {
        path.name
        for path in RUNNER_SRC.rglob("*.py")
        if "merge" in string_constants(path)
    }

    assert spellers == set()
