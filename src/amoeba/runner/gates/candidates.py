"""Which steps would launch or resume this tick (slice 128, D5). Pure.

``launch_candidates`` is the one definition of the set Observe checks, and the
``decide()`` guard relies on it. It recomputes nothing from the store: it reads the
view's dispatch facts and the checkout holders.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.dispatch.facts import StepDispatchFacts
from amoeba.runner.dispatch.params import pipeline_for
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.gates.cf_status import ENTRY_GATE
from amoeba.runner.launch import PARAM_PIPELINE, text_parameter
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import PARAM_CHECKOUT, JournalEntry, Node


@dataclass(frozen=True)
class Candidate:
    """A step that would launch or resume this tick, and where (D5)."""

    node_id: str
    step: LifecycleStep
    state: DispatchState
    checkout: Checkout
    pipeline: str
    slice_index: int
    cf_project_id: str

    @property
    def resume(self) -> bool:
        """Whether this continues a paused run rather than starting one."""
        return self.state is DispatchState.RESUME

    @property
    def needs_gate(self) -> bool:
        """Whether CF's entry gate is read: a fresh or reissued ``tasks`` or
        ``implementation`` launch. A resume continues work already past its gate."""
        return not self.resume and self.step in ENTRY_GATE


def launch_candidates(
    current: Sequence[Node],
    facts: Mapping[str, StepDispatchFacts],
    holders: Mapping[Path, frozenset[str]],
) -> tuple[Candidate, ...]:
    """The steps Observe checks: those that could launch or resume this tick.

    A candidate is a ``POINTED`` step (its own claim is what holds its checkout); a
    ``REISSUE`` step in a checkout no one holds; or a ``RESUME`` step whose checkout
    is held by no one or only by itself. This is the one definition of the set, and
    the ``decide()`` guard relies on it. Nothing is recomputed from the store.
    """
    found: list[Candidate] = []
    for node in current:
        step_facts = facts.get(node.id)
        if step_facts is None or not isinstance(step_facts.checkout, Checkout):
            continue
        checkout = step_facts.checkout
        if step_facts.state is DispatchState.REISSUE:
            checkout = _entry_checkout(step_facts.reissue_of, checkout)
        elif step_facts.state is DispatchState.RESUME:
            checkout = _entry_checkout(step_facts.continues, checkout)
        held_by = holders.get(checkout.path, frozenset[str]())
        if step_facts.state is DispatchState.POINTED:
            pipeline = pipeline_for(step_facts.step)
        elif step_facts.state is DispatchState.REISSUE and not held_by:
            pipeline = _pipeline_of(step_facts.reissue_of)
        elif step_facts.state is DispatchState.RESUME and held_by <= {node.id}:
            pipeline = _pipeline_of(step_facts.continues)
        else:
            continue
        found.append(
            Candidate(
                node.id,
                step_facts.step,
                step_facts.state,
                checkout,
                pipeline,
                step_facts.slice_index,
                step_facts.cf_project_id,
            )
        )
    return tuple(found)


def _entry_checkout(entry: JournalEntry | None, resolved: Checkout) -> Checkout:
    """Where a reissue or resume acts: the checkout its entry recorded.

    The resolved checkout supplies the worktree id when it is the same directory.
    """
    if entry is None:
        raise ValueError("a reissue or resume step has no entry to take its checkout")
    path = Path(text_parameter(entry, PARAM_CHECKOUT))
    return Checkout(path, resolved.worktree_id if path == resolved.path else None)


def _pipeline_of(entry: JournalEntry | None) -> str:
    if entry is None:
        raise ValueError(
            "a reissue or resume step carries no entry to take its pipeline"
        )
    return text_parameter(entry, PARAM_PIPELINE)
