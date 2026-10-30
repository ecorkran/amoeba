"""Helpers for the resolution tests that run the real tick over the dispatch rig."""

from __future__ import annotations

from sq_stub_scripts import RunScript, single_review

from amoeba.process import RunOutcome, RunOutcomeDocument
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import CFReference, Node, NodeKind
from runner.dispatch.tick_rig import CF_PROJECT, DispatchRig
from runner.resolutions.resolution_support import PAUSED_AT

#: The slice's name after the pointer write renames it, in the stub CF's own words.
CF_SLUG = "run-dispatch-and-outcome-ingestion"
STATED_CONCERNS = "verdict: CONCERNS"
INDEX = 125
PROJECT = "demo"

#: A paused run's checkpoint at a loop, as an outcome document carries it.
LOOP_CHECKPOINT = {
    "kind": "loop_exhausted",
    "is_loop": True,
    "paused_at": PAUSED_AT.isoformat(),
}


def write_review(rig: DispatchRig, verdict: str = STATED_CONCERNS) -> RunScript:
    """The captured review with its stated verdict set, written into the checkout."""
    script = single_review(CF_SLUG)
    for path, text in script.files.items():
        target = rig.world.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.replace(STATED_CONCERNS, verdict, 1), encoding="utf-8")
    return script


def answer_poll(
    rig: DispatchRig, run_id: str, outcome: RunOutcome, **fields: object
) -> None:
    """Queue the next ``sq runs wait`` answer for the run."""
    rig.tick_rig.poll.answers.append(
        RunOutcomeDocument.model_validate(
            {"run_id": run_id, "outcome": outcome.value, **fields}
        )
    )


def launched_step(rig: DispatchRig, name: str) -> tuple[Node, Node]:
    """``(slice, step)``: a slice design step with its run in flight."""
    slice_node, step = rig.slice_and_step(name, INDEX)
    rig.tick()
    return slice_node, step


def tasks_step(rig: DispatchRig, slice_node: Node) -> Node:
    """The successor of the slice design step."""
    return rig.store.create_node(
        project_id=PROJECT,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title=LifecycleStep.TASKS.value,
        parent_id=slice_node.id,
        cf=CFReference(project=CF_PROJECT, phase=LifecycleStep.TASKS.value),
    )
