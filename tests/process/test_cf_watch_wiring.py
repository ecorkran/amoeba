"""``start`` wiring: the tenant is third, and ``cf --version`` is captured once."""

from __future__ import annotations

from pathlib import Path

import pytest

import amoeba.process.tenants as tenants_module
from amoeba.process.cf_watch import CFWatchTenant
from amoeba.process.inbox_tenant import InboxTenant
from amoeba.process.review_detection import ReviewDetectionTenant
from amoeba.process.settings import ProcessSettings
from amoeba.process.version_label import VERSION_UNAVAILABLE


def _cf_tenant(supervisor_dir: Path, settings: ProcessSettings) -> CFWatchTenant:
    tenants = tenants_module.standard_tenants(settings, supervisor_dir)
    assert isinstance(tenants[0], InboxTenant)
    assert isinstance(tenants[1], ReviewDetectionTenant)
    assert isinstance(tenants[2], CFWatchTenant)
    assert len(tenants) == 3
    return tenants[2]


def test_the_cf_label_is_captured_once_and_reaches_the_tenant(
    supervisor_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[float] = []

    def capture(timeout_seconds: float) -> str:
        calls.append(timeout_seconds)
        return "cf 9.9.9"

    monkeypatch.setattr(tenants_module, "capture_cf_version_label", capture)
    tenant = _cf_tenant(supervisor_dir, ProcessSettings())

    assert calls == [ProcessSettings().cf_timeout_seconds]
    assert tenant.version_label == "cf 9.9.9"


def test_with_no_cf_on_path_the_label_is_the_unavailable_marker(
    supervisor_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    tenant = _cf_tenant(supervisor_dir, ProcessSettings())

    assert tenant.version_label == VERSION_UNAVAILABLE


def test_the_data_file_is_projects_json_in_the_configured_directory(
    supervisor_dir: Path, tmp_path: Path
) -> None:
    cf_dir = tmp_path / "cf"
    cf_dir.mkdir()
    (cf_dir / "projects.json").write_text("[]")

    tenant = _cf_tenant(supervisor_dir, ProcessSettings(cf_data_dir=cf_dir))

    assert tenant.name == "cf-watch"
    assert tenant.data_file == cf_dir / "projects.json"
