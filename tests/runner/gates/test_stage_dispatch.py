"""D5: GateStage.check_dispatch reads for the candidates and returns their results."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from cf_stub import write_cf_stub
from cf_stub_gates import CONFIG_MODE_ENV, GateMode

from amoeba.runner.decide import ProjectView
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.faults import FaultKind, NodeContext, TickFaults
from amoeba.runner.gates.predispatch import Block, Ok
from amoeba.runner.gates.stage import GateStage
from amoeba.runner.lifecycle.plan_read import CF_KEY_INTEGRATION_BRANCH
from amoeba.store import Store
from runner.dispatch.dispatch_support import facts, view_of
from runner.dispatch.pointer_support import budget_allowing, generous_budget
from runner.gate_rig import (
    config_knobs,
    git_checkout,
    single_status_knobs,
    status_fixture,
)

SLICE = 125


class Setup:
    def __init__(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, store: Store
    ) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.checkout = git_checkout(tmp_path / "checkout")
        bin_dir = write_cf_stub(tmp_path / "bin")
        monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
        fixture = status_fixture(tmp_path / "s.json", "in_implementation", SLICE)
        for name, value in {
            **single_status_knobs(fixture),
            **config_knobs(tmp_path, {}),
        }.items():
            monkeypatch.setenv(name, value)
        self.stage = GateStage(
            store=store,
            project_id="demo",
            context=NodeContext(),
            cf_run=subprocess.run,
            call_timeout_seconds=20.0,
            amoeba_version="amoeba-test",
        )

    def view(self) -> ProjectView:
        return view_of(
            {"a": facts(DispatchState.READY, self.checkout, slice_index=SLICE)}
        )


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, store: Store) -> Setup:
    return Setup(tmp_path, monkeypatch, store)


def test_a_clean_checkout_puts_ok_in_the_view(setup: Setup) -> None:
    result = setup.stage.check_dispatch(setup.view(), generous_budget(), TickFaults())

    assert result.cut_off is False
    assert isinstance(result.checks["a"], Ok)
    assert result.checks["a"].evidence["branch"] == "main"


def test_a_pointed_step_on_a_dirty_checkout_puts_a_block(setup: Setup) -> None:
    (setup.checkout / "README.md").write_text("changed\n")

    result = setup.stage.check_dispatch(setup.view(), generous_budget(), TickFaults())

    block = result.checks["a"]
    assert isinstance(block, Block) and block.fault_kind is FaultKind.CHECKOUT_DIRTY
    assert block.payload["paths"] == ["README.md"]


def test_a_failed_read_puts_nothing_and_raises_checkout_read_failed(
    setup: Setup,
) -> None:
    setup.monkeypatch.setenv(CONFIG_MODE_ENV, GateMode.FAIL.value)
    faults = TickFaults()

    result = setup.stage.check_dispatch(setup.view(), generous_budget(), faults)

    assert result.checks == {}
    [fault] = list(faults)
    assert fault.kind is FaultKind.CHECKOUT_READ_FAILED
    assert fault.node_id == "a"
    assert fault.extra is not None
    assert fault.extra["checkout"] == str(setup.checkout)
    assert fault.extra["command"] == f"cf config get {CF_KEY_INTEGRATION_BRANCH}"
    assert "reason" in fault.extra


def test_a_cut_off_stops_the_pass_and_says_so(setup: Setup) -> None:
    result = setup.stage.check_dispatch(setup.view(), budget_allowing(1), TickFaults())

    assert result.cut_off is True and result.checks == {}


def test_a_step_that_is_not_a_candidate_is_not_read(setup: Setup) -> None:
    view = view_of({"a": facts(DispatchState.IN_FLIGHT, setup.checkout)})

    result = setup.stage.check_dispatch(view, generous_budget(), TickFaults())

    assert result.checks == {} and result.cut_off is False
