"""An in-process host for driving ``InboxTenant.tick`` directly.

``LocalHost`` satisfies the tenant's ``InboxHost`` protocol with **real**
project stores opened by the real ``ProjectStores`` — only the process
lifetime around them is absent. Tests of the full process, signals and
restarts included, use ``host_harness`` instead.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.process.project_stores import ProjectStores
from amoeba.process.settings import ProcessSettings
from amoeba.store import Store


class LocalHost:
    """Real stores, a settable stop flag, and no process around them."""

    def __init__(self, supervisor_dir: Path, settings: ProcessSettings) -> None:
        self.settings = settings
        self.stop_requested = False
        self.stores = ProjectStores(supervisor_dir)
        self.stores.open_all()

    @property
    def project_ids(self) -> tuple[str, ...]:
        return self.stores.project_ids

    def store_for(self, project_id: str) -> Store:
        return self.stores.store_for(project_id)

    def open_project(self, project_id: str) -> Store:
        return self.stores.open_project(project_id)
