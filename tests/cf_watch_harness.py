"""Rig for driving ``CFWatchTenant`` in-process over real stores and a scratch CF dir.

Real stores through ``LocalHost``, a fake monotonic clock and a fake wall clock,
and a data file written by temp-file-and-rename as Context Forge writes it.
Helpers hold no assertions.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cf_fixture import fixture_bytes
from detection_harness import FakeClock
from local_host_harness import LocalHost

from amoeba.process.cf_watch import CFWatchTenant
from amoeba.process.settings import ProcessSettings
from amoeba.store import CFSnapshot, Store, SubmissionKind
from amoeba.store.inbox_models import LINK_CF_PROJECT_ID

PROJECT = "demo"
LABEL = "cf-test-label 0.0.0"
SUBMITTED_AT = datetime(2026, 10, 16, tzinfo=UTC)
WALL_START = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


class FakeWallClock:
    """A datetime that advances one second per read, so each check differs."""

    def __init__(self) -> None:
        self._reads = 0

    def __call__(self) -> datetime:
        self._reads += 1
        return WALL_START + timedelta(seconds=self._reads)


class CFRig:
    """One project, one scratch CF directory, one tenant."""

    def __init__(self, host: LocalHost, cf_dir: Path, *, label: str = LABEL) -> None:
        self.host = host
        self.data_file = cf_dir / "projects.json"
        self.clock = FakeClock()
        self.wall = FakeWallClock()
        self.store: Store = host.open_project(PROJECT)
        self.tenant = self.new_tenant(label=label)
        self._submissions = 0

    @property
    def interval(self) -> float:
        return ProcessSettings().cf_scan_interval_seconds

    def new_tenant(self, *, label: str = LABEL) -> CFWatchTenant:
        """A fresh tenant over the same store and file: what a restart builds."""
        return CFWatchTenant(
            version_label=label,
            data_file=self.data_file,
            clock=self.clock,
            wall_clock=self.wall,
        )

    def link(self, cf_project_id: str, project_id: str = PROJECT) -> None:
        self._submissions += 1
        store = self.host.open_project(project_id)
        store.apply_submission(
            submission_id=f"link-{self._submissions}",
            project_id=project_id,
            kind=SubmissionKind.LINK_CF_PROJECT,
            submitted_by="pm",
            submitted_at=SUBMITTED_AT,
            payload={LINK_CF_PROJECT_ID: cf_project_id},
        )

    def write(self, data: bytes | None = None) -> None:
        """Replace the data file by temp-file-and-rename (a new inode, as CF does)."""
        temporary = self.data_file.with_name(self.data_file.name + ".tmp")
        temporary.write_bytes(fixture_bytes() if data is None else data)
        os.replace(temporary, self.data_file)

    def tick(self, tenant: CFWatchTenant | None = None) -> bool:
        """Move the clock past one interval, then tick."""
        self.clock.now += self.interval
        return (tenant or self.tenant).tick(self.host)

    def snapshots(self, project_id: str = PROJECT) -> list[CFSnapshot]:
        return self.host.open_project(project_id).cf_snapshots(project_id)
