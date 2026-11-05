"""An in-process host for driving the inbox tenants' ``tick`` directly.

``LocalHost`` satisfies the ``InboxHost`` and ``ProgramInboxHost`` protocols
with **real** project stores and a real program store, opened by the real
``ProjectStores`` — only the process lifetime around them is absent. Tests of
the full process, signals and restarts included, use ``host_harness`` instead.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.process.project_stores import ProjectStores
from amoeba.process.settings import ProcessSettings
from amoeba.store import ProgramStore, Store


class LocalHost:
    """Real stores, a settable stop flag, and no process around them."""

    def __init__(self, supervisor_dir: Path, settings: ProcessSettings) -> None:
        self.settings = settings
        self.stop_requested = False
        self.stores = ProjectStores(supervisor_dir)
        self.stores.open_all()
        self.stores.open_program_store()

    @property
    def project_ids(self) -> tuple[str, ...]:
        return self.stores.project_ids

    def store_for(self, project_id: str) -> Store:
        return self.stores.store_for(project_id)

    def open_project(self, project_id: str) -> Store:
        return self.stores.open_project(project_id)

    @property
    def program_store(self) -> ProgramStore | None:
        return self.stores.program_store

    def ensure_program_store(self) -> ProgramStore:
        return self.stores.ensure_program_store()
