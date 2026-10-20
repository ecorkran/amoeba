"""The tenants ``amoeba start`` registers.

Kept apart from the CLI so a program that hosts its own tenant (initiative 120's
Runner) composes the shipped ones as ``(*standard_tenants(...), runner)``
without importing ``amoeba.cli``.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.process.cf_watch import CFWatchTenant
from amoeba.process.host import Tenant
from amoeba.process.inbox_tenant import InboxTenant
from amoeba.process.observers.cf_readback import (
    capture_version_label as capture_cf_version_label,
)
from amoeba.process.review_detection import ReviewDetectionTenant
from amoeba.process.settings import ProcessSettings
from amoeba.process.version_label import capture_sq_version_label
from amoeba.upstream.context_forge import PROJECTS_FILE_NAME


def standard_tenants(
    settings: ProcessSettings, supervisor_dir: Path
) -> tuple[Tenant, ...]:
    """The tenants ``start`` registers, in tick order.

    ``sq --version`` and ``cf --version`` are captured here, once, before the
    loop: no tick ever starts a subprocess. Recovery still runs before any
    tenant ticks, inside ``ResidentProcess.run``.
    """
    sq_label = capture_sq_version_label(settings.sq_timeout_seconds)
    cf_label = capture_cf_version_label(settings.cf_timeout_seconds)
    # Tenants tick in registration order. The inbox is first, so a backlog of
    # submissions — ``watch_reviews`` and ``link_cf_project`` included — drains
    # ahead of detection and the Context Forge watch.
    return (
        InboxTenant(supervisor_dir),
        ReviewDetectionTenant(version_label=sq_label),
        CFWatchTenant(
            version_label=cf_label,
            data_file=settings.cf_data_dir / PROJECTS_FILE_NAME,
        ),
    )
