"""The factory validates bounds, creates the log directory and probes ``sq``."""

from __future__ import annotations

import dataclasses
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import pytest
from sq_stub import write_sq_stub

from amoeba.process import ProcessSettings, StartupFailedError
from amoeba.runner import RunnerTenant, factory, runner_tenant
from amoeba.runner.decide import Action, ProjectView
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.factory import PRODUCTION_PLANNERS
from amoeba.runner.project_config import PROJECT_DEFAULTS, ProjectConfig
from amoeba.runner.resolutions.planner import ContinuationPlanner
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


def _planners_given_to_the_tenant(
    monkeypatch: pytest.MonkeyPatch, healthy_sq: Path, **kwargs: Any
) -> tuple[object, ...]:
    """Build a tenant through the factory and return the planners it was handed."""
    captured: list[tuple[object, ...]] = []

    def spy(**tenant_kwargs: Any) -> RunnerTenant:
        captured.append(tuple(tenant_kwargs["planners"]))
        return RunnerTenant(**tenant_kwargs)

    monkeypatch.setattr(factory, "RunnerTenant", spy)
    runner_tenant(ProcessSettings(), healthy_sq, **kwargs)
    [planners] = captured
    return planners


def test_the_production_tuple_is_dispatch_then_continuations() -> None:
    assert [type(planner) for planner in PRODUCTION_PLANNERS] == [
        DispatchPlanner,
        ContinuationPlanner,
    ]


def test_no_planners_selects_the_production_tuple(
    monkeypatch: pytest.MonkeyPatch, healthy_sq: Path
) -> None:
    planners = _planners_given_to_the_tenant(monkeypatch, healthy_sq)
    assert planners == PRODUCTION_PLANNERS


def test_a_passed_value_overrides_the_production_tuple(
    monkeypatch: pytest.MonkeyPatch, healthy_sq: Path
) -> None:
    planners = _planners_given_to_the_tenant(monkeypatch, healthy_sq, planners=())
    assert planners == ()


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


def test_the_tenant_holds_the_installed_version(
    monkeypatch: pytest.MonkeyPatch, healthy_sq: Path
) -> None:
    captured: list[dict[str, Any]] = []

    def spy(**tenant_kwargs: Any) -> RunnerTenant:
        captured.append(tenant_kwargs)
        return RunnerTenant(**tenant_kwargs)

    monkeypatch.setattr(factory, "RunnerTenant", spy)

    runner_tenant(ProcessSettings(), healthy_sq)

    [kwargs] = captured
    assert kwargs["amoeba_version"] == version("amoeba")


def test_an_unreadable_package_version_fails_start(
    monkeypatch: pytest.MonkeyPatch, healthy_sq: Path
) -> None:
    def not_installed(name: str) -> str:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(factory, "version", not_installed)

    with pytest.raises(StartupFailedError, match="installed version"):
        runner_tenant(ProcessSettings(), healthy_sq)


def _settings_with_project_config(path: Path) -> ProcessSettings:
    return dataclasses.replace(ProcessSettings(), project_config_path=path)


def test_the_tenant_holds_the_project_config_the_file_gives(
    monkeypatch: pytest.MonkeyPatch, healthy_sq: Path, tmp_path: Path
) -> None:
    config_file = tmp_path / "projects.yaml"
    config_file.write_text("projects:\n  scratch:\n    pipeline: p456\n")
    captured: list[dict[str, Any]] = []

    def spy(**tenant_kwargs: Any) -> RunnerTenant:
        captured.append(tenant_kwargs)
        return RunnerTenant(**tenant_kwargs)

    monkeypatch.setattr(factory, "RunnerTenant", spy)

    runner_tenant(_settings_with_project_config(config_file), healthy_sq)

    [kwargs] = captured
    config = kwargs["project_config"]
    assert config.for_project("scratch").pipeline == "p456"
    assert config.for_project("amoeba") == PROJECT_DEFAULTS


def test_with_no_project_config_every_project_takes_the_defaults(
    monkeypatch: pytest.MonkeyPatch, healthy_sq: Path
) -> None:
    captured: list[dict[str, Any]] = []

    def spy(**tenant_kwargs: Any) -> RunnerTenant:
        captured.append(tenant_kwargs)
        return RunnerTenant(**tenant_kwargs)

    monkeypatch.setattr(factory, "RunnerTenant", spy)

    runner_tenant(ProcessSettings(), healthy_sq)

    assert captured[0]["project_config"] == ProjectConfig()


def test_an_invalid_project_config_fails_start_before_anything_is_created(
    healthy_sq: Path, tmp_path: Path
) -> None:
    config_file = tmp_path / "projects.yaml"
    config_file.write_text("projects:\n  scratch:\n    merge_policy: auto\n")

    with pytest.raises(StartupFailedError, match="merge_policy"):
        runner_tenant(_settings_with_project_config(config_file), healthy_sq)

    assert not healthy_sq.exists()
