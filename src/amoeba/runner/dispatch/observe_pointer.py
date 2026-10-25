"""Observe the CF pointer: finish open pointer writes and confirm pointed steps.

Two kinds of read-back, each one ``cf get --json`` in the step's checkout, each under
the tick budget, and both through the one read-back function (D2, D3):

- every unresolved pointer write (a ``cf_write`` the Runner issued) is read back and
  settled as 6.3 describes. This is how a write cut off between ``cf set`` and its
  read-back, or by a crash, is finished. A read that fails stays open and is tried
  again next tick; once ``launch_grace_seconds`` have passed since the entry was
  issued and it still fails, the entry goes through ``journal_escalate`` with the
  last failure, so a CF that stays unreadable ends in a human and not a loop.
- every current step whose journal says it was pointed is read once more, now:
  the step counts as pointed only while CF still points at its slice, and a scan
  would not tell, because the CF watch records a snapshot only when the projection
  changes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.cf_call import CfRun
from amoeba.runner.decide import WriteSlicePointer
from amoeba.runner.dispatch.pointer import (
    Confirmed,
    PointerAnswer,
    PointerReadFailed,
    PointerUnknown,
    expected_checkout,
    issue_pointer_write,
    read_back,
)
from amoeba.runner.dispatch.pointer_apply import apply_answer, apply_attempt
from amoeba.runner.dispatch.state import DispatchState, dispatch_state
from amoeba.runner.faults import NodeContext
from amoeba.runner.intent.governance import DesiredStateIndex, current_steps
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import CommandKind, JournalEntry, Node, Store


@dataclass(frozen=True)
class PointerObservation:
    """What the pointer stage found this tick."""

    #: Nodes of the current steps whose pointer CF confirmed just now.
    confirmed: frozenset[str]
    #: ``CUT_OFF`` if the budget refused a read-back: nothing may be decided on.
    result: TickResult
    #: Whether the stage wrote to the store.
    wrote: bool


class PointerStage:
    """Reads CF back for pointer writes. Holds only its collaborators."""

    def __init__(
        self,
        run: CfRun,
        timeout_seconds: float,
        grace_seconds: float,
        now: Callable[[], datetime],
    ) -> None:
        self._run = run
        self._timeout_seconds = timeout_seconds
        self._grace_seconds = grace_seconds
        self._now = now

    def observe_project(
        self,
        store: Store,
        project_id: str,
        desired: DesiredStateIndex,
        budget: TickBudget,
        context: NodeContext,
    ) -> PointerObservation:
        """:meth:`observe` over the project's current steps, from the store's tree.

        Reads the tree as it is after the plan stage; the view is built again
        afterwards, because settling a write can block a step.
        """
        tree = LifecycleTree(store.nodes_for_project(project_id))
        return self.observe(
            store,
            project_id,
            current_steps(tree, desired),
            drives=desired.drives_anything(),
            budget=budget,
            context=context,
        )

    def observe(
        self,
        store: Store,
        project_id: str,
        current: Sequence[Node],
        *,
        drives: bool,
        budget: TickBudget,
        context: NodeContext,
    ) -> PointerObservation:
        """Settle open pointer writes, then confirm the pointed current steps.

        ``drives`` is 124's predicate: the pointed-step read-backs happen only for a
        project the PM drives. Open pointer writes are finished regardless.
        """
        wrote = False
        for entry in store.unresolved_journal_entries(project_id):
            if entry.kind is not CommandKind.CF_WRITE:
                continue
            if expected_checkout(entry) is None:
                continue  # not a Runner pointer write; recovery's to settle
            if not budget.allows_call():
                return PointerObservation(frozenset(), TickResult.CUT_OFF, wrote)
            context.set(entry.node_id)
            wrote = self._settle(store, entry) or wrote
        confirmed: set[str] = set()
        if drives:
            for node in current:
                step_entries = store.journal_entries(project_id, node_id=node.id)
                if _journal_says_pointed(step_entries):
                    if not budget.allows_call():
                        return PointerObservation(
                            frozenset(), TickResult.CUT_OFF, wrote
                        )
                    context.set(node.id)
                    if self._confirms(step_entries[-1]):
                        confirmed.add(node.id)
        context.clear()
        return PointerObservation(frozenset(confirmed), TickResult.COMPLETE, wrote)

    def write(
        self, store: Store, action: WriteSlicePointer, budget: TickBudget
    ) -> None:
        """Act on a pointer-write action: journal, ``cf set``, read back, apply (D2).

        Writes nothing if the budget refuses the first call. A write cut off before
        its read-back is left open; the next tick's :meth:`observe` finishes it.
        """
        attempt = issue_pointer_write(
            store, action, self._run, self._timeout_seconds, budget
        )
        if attempt is not None:
            apply_attempt(store, attempt)

    def _answer(self, entry: JournalEntry) -> PointerAnswer:
        expected = expected_checkout(entry)
        if expected is None:
            # Escalating resolves it once; raising would recur every tick.
            return PointerUnknown(
                reason=f"entry {entry.id} lacks the keys of a pointer write"
            )
        return read_back(entry, expected, self._run, self._timeout_seconds)

    def _settle(self, store: Store, entry: JournalEntry) -> bool:
        """Apply the read-back to an open entry. Returns whether the store changed."""
        answer = self._answer(entry)
        if not isinstance(answer, PointerReadFailed):
            apply_answer(store, entry, answer)
            return True
        if self._past_grace(entry):
            store.journal_escalate(
                entry.id,
                reason=(
                    f"{answer.reason}; unreadable for over "
                    f"{self._grace_seconds:g}s since the write was issued"
                ),
            )
            return True
        return False

    def _confirms(self, entry: JournalEntry) -> bool:
        """Whether CF still holds ``entry``'s slice; false if it is no pointer write."""
        expected = expected_checkout(entry)
        if expected is None:
            return False
        answer = read_back(entry, expected, self._run, self._timeout_seconds)
        return isinstance(answer, Confirmed)

    def _past_grace(self, entry: JournalEntry) -> bool:
        if entry.issued_at is None:
            return True  # an entry with no issue time cannot be waited on
        return (self._now() - entry.issued_at).total_seconds() >= self._grace_seconds


def _journal_says_pointed(entries: Sequence[JournalEntry]) -> bool:
    return (
        dispatch_state(entries, None, pointer_confirmed=True) is DispatchState.POINTED
    )
