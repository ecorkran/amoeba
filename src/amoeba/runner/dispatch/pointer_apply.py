"""Turn what a pointer write did into store writes (D2's outcome bullets).

Applied the same way whether the read-back happened in the tick that wrote the
pointer or in a later one, so a crash between the write and the read-back is finished
by the next tick through the same code:

=============================  ==================================================
what happened                  what is written
=============================  ==================================================
read back: confirmed           the entry resolves ``completed`` with the record's
                               file slice, worktree, path and ``updatedAt``; the
                               slice node's ``slice_name`` is set from the stem
read back: another index,      the step blocks on a human with
path or worktree               ``pointer_write_failed``; the entry resolves ``failed``
read back: cannot be judged    ``journal_escalate``, at once
read back: could not be read   nothing: the entry stays open and is read again
``cf set`` exited non-zero     as a mismatch, with the head of CF's output
``cf set`` timed out           nothing: the write may have landed; read back later
=============================  ==================================================
"""

from __future__ import annotations

import dataclasses

from amoeba.runner.dispatch.pointer import (
    Confirmed,
    Mismatch,
    PointerAnswer,
    PointerAttempt,
    PointerReadFailed,
    PointerUnknown,
    SetCutOff,
    SetDone,
    SetFailed,
)
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, FaultKind
from amoeba.runner.ingest.outcome import PAYLOAD_REASON, BlockPlan, cut_to_bound
from amoeba.runner.ingest.record import block_once
from amoeba.store import BlockedKind, JournalEntry, JournalOutcome, NodeKind, Store


def apply_attempt(store: Store, attempt: PointerAttempt) -> None:
    """Apply what a fresh pointer write did: the ``cf set``, then any read-back."""
    match attempt.set_result:
        case SetFailed(exit_code=code, detail=detail):
            _fail(store, attempt.entry, f"cf set exited {code}: {detail}")
        case SetCutOff():
            return  # it may have landed; the next tick reads back
        case SetDone():
            if attempt.answer is not None:
                apply_answer(store, attempt.entry, attempt.answer)


def apply_answer(store: Store, entry: JournalEntry, answer: PointerAnswer) -> None:
    """Apply a read-back's answer to an unresolved pointer-write entry."""
    match answer:
        case Confirmed():
            _confirm(store, entry, answer)
        case Mismatch(reason=reason):
            _fail(store, entry, reason)
        case PointerUnknown(reason=reason):
            store.journal_escalate(entry.id, reason=reason)
        case PointerReadFailed():
            return  # transient: the entry stays open and is read again


def _confirm(store: Store, entry: JournalEntry, answer: Confirmed) -> None:
    node = store.get_node(entry.node_id)
    parent = (
        None
        if node is None or node.parent_id is None
        else store.get_node(node.parent_id)
    )
    if parent is None or parent.kind is not NodeKind.SLICE:
        raise ValueError(f"the step of entry {entry.id} has no slice node to name")
    if parent.cf.slice_name != answer.stem.name:
        store.update_cf_reference(
            parent.id, dataclasses.replace(parent.cf, slice_name=answer.stem.name)
        )
    store.journal_resolve(
        entry.id, outcome=JournalOutcome.COMPLETED, result=dict(answer.result)
    )


def _fail(store: Store, entry: JournalEntry, reason: str) -> None:
    """Block the step on a human, then resolve the entry ``failed`` (in that order)."""
    bounded = cut_to_bound(reason)
    block_once(
        store,
        entry.node_id,
        BlockPlan(
            BlockedKind.HUMAN,
            f"the CF slice pointer write failed: {bounded}",
            {
                PAYLOAD_FAULT_KIND: FaultKind.POINTER_WRITE_FAILED.value,
                PAYLOAD_REASON: bounded,
            },
        ),
    )
    store.journal_resolve(
        entry.id, outcome=JournalOutcome.FAILED, result={PAYLOAD_REASON: bounded}
    )
