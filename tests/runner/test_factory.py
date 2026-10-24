"""The factory validates bounds, creates the log directory and probes ``sq``."""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest
from sq_stub import write_sq_stub

from amoeba.process import ProcessSettings, StartupFailedError
from amoeba.runner import RunnerTenant, runner_tenant
from amoeba.runner.decide import Action, ProjectView
from amoeba.runner.factory import PRODUCTION_PLANNERS
from amoeba.store import Store


@pytest.fixture
def healthy_sq(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stub ``sq`` first on PATH under a throwaway HOME."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    bin_dir = write_sq_stub(tmp_path / "bin")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    return tmp_path / "supervisor"


def test_the_production_tuple_is_empty() -> None:
    assert PRODUCTION_PLANNERS == ()


def test_a_build_creates_the_launch_logs_directory(healthy_sq: Path) -> None:
    tenant = runner_tenant(ProcessSettings(), healthy_sq)

    assert isinstance(tenant, RunnerTenant) and tenant.name == "runner"
    assert (healthy_sq / "launch-logs").is_dir()


def test_a_second_build_over_an_existing_directory_succeeds(healthy_sq: Path) -> None:
    runner_tenant(ProcessSettings(), healthy_sq)
    runner_tenant(ProcessSettings(), healthy_sq)


@pytest.mark.parametrize(
    "field",
    [
        "tick_deadline_seconds",
        "tick_call_timeout_seconds",
        "run_poll_interval_seconds",
        "plan_read_interval_seconds",
    ],
)
@pytest.mark.parametrize("value", [0.0, -1.0])
def test_a_non_positive_bound_fails_naming_the_field(
    healthy_sq: Path, field: str, value: float
) -> None:
    settings = dataclasses.replace(ProcessSettings(), **{field: value})

    with pytest.raises(StartupFailedError, match=field):
        runner_tenant(settings, healthy_sq)

    assert not healthy_sq.exists(), "nothing was created before validation"


def test_a_call_timeout_not_below_the_shutdown_grace_fails(healthy_sq: Path) -> None:
    settings = ProcessSettings(
        tick_call_timeout_seconds=10.0, shutdown_grace_seconds=10.0
    )

    with pytest.raises(StartupFailedError, match="tick_call_timeout_seconds"):
        runner_tenant(settings, healthy_sq)


def test_a_failed_sq_probe_surfaces_as_startup_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    with pytest.raises(StartupFailedError, match="runs wait"):
        runner_tenant(ProcessSettings(), tmp_path / "supervisor")


def test_passed_planners_are_consulted_by_a_tick(
    healthy_sq: Path, store: Store
) -> None:
    class Recording:
        def __init__(self) -> None:
            self.seen: list[str] = []

        def plan(self, view: ProjectView) -> list[Action]:
            self.seen.append(view.project_id)
            return []

    class Host:
        stop_requested = False
        project_ids = ("demo",)

        def store_for(self, project_id: str) -> Store:
            return store

    planner = Recording()
    tenant = runner_tenant(ProcessSettings(), healthy_sq, planners=(planner,))

    tenant.tick(Host())

    assert planner.seen == ["demo"]
