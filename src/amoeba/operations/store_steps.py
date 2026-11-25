"""The ``Steps`` protocol client-run commands call, and the local way (262 D3).

``LocalSteps`` runs each step on the local store in process, each as its own
transaction as today. ``DoorSteps`` (``wiring_steps``) sends each as one door call.
"""

from __future__ import annotations

from typing import Protocol

from amoeba.operations.steps.dispatch import StepEdges, run_step
from amoeba.operations.steps.models import Step, StepModel
from amoeba.operations.steps.work import work_waiting
from amoeba.store.machines import acting_machine_id
from amoeba.store.store import Store


class Steps(Protocol):
    """One method: run ``step`` with ``request`` and give its reply model."""

    def run[Request: StepModel, Reply: StepModel](
        self, step: Step[Request, Reply], request: Request
    ) -> Reply: ...


class LocalSteps:
    """``run_step`` on a store opened by the caller, who keeps it open."""

    def __init__(self, store: Store, edges: StepEdges) -> None:
        self._store = store
        self._edges = edges

    def run[Request: StepModel, Reply: StepModel](
        self, step: Step[Request, Reply], request: Request
    ) -> Reply:
        reply = run_step(
            step.name, self._store, request.model_dump(mode="json"), self._edges
        )
        if not isinstance(reply, step.reply):
            raise AssertionError(f"step {step.name} gave a {type(reply).__name__}")
        return reply

    @property
    def store(self) -> Store:
        """The open store, for the local placements that run beside the steps (a
        repo's first ``add``)."""
        return self._store

    def work_waiting(self) -> bool:
        """The work flag for the calling machine: one read of ``work_waiting``. A door
        reply carries it instead, so this is the local way's one extra read (D10)."""
        config = self._edges.load_config()
        with self._store.read() as transaction:
            return work_waiting(
                transaction,
                acting_machine_id(transaction),
                config,
                self._edges.clock(),
                self._edges.door_version,
            )
