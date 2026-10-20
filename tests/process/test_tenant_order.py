"""``amoeba start`` registers exactly these tenants, in exactly this order.

Tenants tick in registration order, so a reorder changes behavior: the inbox
must drain ahead of detection and the Context Forge watch. The expected tuple is
written out literally, never derived from the code under test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import amoeba.process.tenants as tenants_module
from amoeba.process.settings import ProcessSettings

EXPECTED_TENANT_NAMES = ("inbox", "review-detection", "cf-watch")


def _fixed_label(timeout_seconds: float) -> str:
    """Stands in for the ``capture_*_version_label`` functions."""
    return "fixed test label"


def test_the_registered_tenants_and_their_order_are_pinned(
    supervisor_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No sq/cf subprocess may run while the tuple is built.
    monkeypatch.setattr(tenants_module, "capture_sq_version_label", _fixed_label)
    monkeypatch.setattr(tenants_module, "capture_cf_version_label", _fixed_label)
    settings = ProcessSettings(
        cf_data_dir=tmp_path / "context-forge", sq_runs_dir=tmp_path / "sq-runs"
    )

    tenants = tenants_module.standard_tenants(settings, supervisor_dir)

    assert len(tenants) == 3
    assert tuple(tenant.name for tenant in tenants) == EXPECTED_TENANT_NAMES
