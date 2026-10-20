"""``start`` wiring: the sq label is captured once, and no tick runs a subprocess."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from detection_harness import (
    PROJECT,
    ROUND_ONE_PART_ONE,
    ROUND_TWO_PART_ONE,
    DetectionRig,
)

import amoeba.process.tenants as tenants_module
from amoeba.process.inbox_tenant import InboxTenant
from amoeba.process.review_detection import ReviewDetectionTenant
from amoeba.process.settings import ProcessSettings
from amoeba.process.version_label import VERSION_UNAVAILABLE
from amoeba.store import DetectionOutcome


def _detection_tenant(supervisor_dir: Path) -> ReviewDetectionTenant:
    tenants = tenants_module.standard_tenants(ProcessSettings(), supervisor_dir)
    assert isinstance(tenants[0], InboxTenant)
    assert isinstance(tenants[1], ReviewDetectionTenant)
    return tenants[1]


def test_the_label_is_captured_once_and_reaches_the_tenant(
    supervisor_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[float] = []

    def capture(timeout_seconds: float) -> str:
        calls.append(timeout_seconds)
        return "sq 9.9.9"

    monkeypatch.setattr(tenants_module, "capture_sq_version_label", capture)
    tenant = _detection_tenant(supervisor_dir)

    assert calls == [ProcessSettings().sq_timeout_seconds]
    assert tenant.version_label == "sq 9.9.9"


def test_with_no_sq_on_path_the_label_is_unavailable(
    supervisor_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert _detection_tenant(supervisor_dir).version_label == VERSION_UNAVAILABLE


def test_no_tick_starts_a_subprocess(
    rig: DetectionRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a tick started a subprocess")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    rig.seed_slice_node()
    rig.copy(ROUND_ONE_PART_ONE)
    rig.watch()
    rig.run_scans()
    rig.copy(ROUND_TWO_PART_ONE)
    rig.run_scans(2)

    assert [d.outcome for d in rig.store.detections(PROJECT)] == [
        DetectionOutcome.BASELINE,
        DetectionOutcome.INGESTED,
    ]
