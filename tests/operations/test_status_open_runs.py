"""``status``'s client part asks ``open_runs`` first, and stops there when it fails
(slice 262, D9)."""

from __future__ import annotations

from pathlib import Path

import pytest
from store.decision_support import CORE

from amoeba.client.errors import HubUnreachableError
from amoeba.operations.names import OperationName
from amoeba.operations.steps.model_base import Step, StepModel
from amoeba.store.vocabulary import Door
from amoeba.wiring_gather import gather_values
from operations.status_support import FakeCf, status_deps


class _DeadHub:
    """``Steps`` whose hub never answers; counts what it was asked."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def run[Request: StepModel, Reply: StepModel](
        self, step: Step[Request, Reply], request: Request
    ) -> Reply:
        self.asked.append(step.name)
        raise HubUnreachableError("no reply")


@pytest.mark.parametrize("name", [OperationName.STATUS, OperationName.LIST])
def test_an_open_runs_that_fails_stops_the_call_with_no_further_call(
    tmp_path: Path, name: OperationName
) -> None:
    directory = tmp_path / "core"
    directory.mkdir()
    deps = status_deps(tmp_path, cf=FakeCf({directory: CORE}), runs=[])
    hub = _DeadHub()

    with pytest.raises(HubUnreachableError):
        gather_values(name, {}, directory, Door.CLI, deps, hub)

    assert hub.asked == ["open_runs"]
