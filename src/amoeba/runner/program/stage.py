"""The program stage: which program a project is in, found each tick.

Placed by the architecture directly after intents and resolutions and before
Observe (so a PM resolution is acknowledged before any later program-stage rule
can read the block). In this slice it is **read-only**: one read of the program
store finds the project's program, or ``None``. It opens no member store, writes
nothing, issues nothing and does not change ``tick.wrote``. The tick does not
keep the result; later slices that consume it (183) keep it and grow it into the
view they hand to readiness. The read exists now so the stage's place and its
failure behavior ship and are tested before anything depends on it.

Failures: a ``StoreError`` from the **program store** propagates. It is in
``STORE_FAILURES``, so the tenant re-raises it and the process exits as a store
failure, and because every project's tick reads the program store this stops
projects in no program too. Any other exception is a bug and reaches the
tenant's existing catch as a project-scoped ``unexpected_fault``.
"""

from __future__ import annotations

from amoeba.store import Program, ProgramStore


class ProgramStage:
    """Finds a project's program, for one tick."""

    def __init__(self, program_store: ProgramStore | None) -> None:
        """Hold the host's program store as it is this tick.

        Args:
            program_store: The open program store, or ``None`` while none
                exists. Read from the host every tick, because the store can
                appear at runtime when the first program is registered.
        """
        self._program_store = program_store

    def run(self, project_id: str) -> Program | None:
        """The program ``project_id`` is a member of.

        Returns:
            ``None`` when there is no program store or the project is in no
            program; nothing else is read.

        Raises:
            StoreError: From the program store. Not caught: the process exits.
        """
        if self._program_store is None:
            return None
        return self._program_store.program_of(project_id)
