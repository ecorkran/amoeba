"""Interpret an intent against the lifecycle tree (D2, D3).

``interpret`` is pure: it reads the message, the tree and the target's current row,
and answers with an outcome, a reason and the row change. Rejections are answers,
never exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from amoeba.runner.faults import RUNNER_ACTOR
from amoeba.runner.intent.merge import merge_intent
from amoeba.runner.intent.vocabulary import (
    REASON_DETAIL_LIMIT,
    IntentBody,
    IntentRejection,
    TargetKind,
)
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import (
    AcknowledgmentOutcome,
    ClearDesiredState,
    DesiredState,
    Message,
    Node,
    NodeKind,
    SetDesiredState,
    Store,
)


@dataclass(frozen=True)
class Interpretation:
    """What to record for one intent: the outcome, why, and the row change if any."""

    outcome: AcknowledgmentOutcome
    reason: str | None = None
    desired_state: SetDesiredState | ClearDesiredState | None = None


def _rejected(code: IntentRejection, detail: str) -> Interpretation:
    reason = f"{code.value}: {detail[:REASON_DETAIL_LIMIT]}"
    return Interpretation(AcknowledgmentOutcome.REJECTED, reason)


def _target_kind(node: Node) -> TargetKind | None:
    """The node's kind, or ``None`` for a node that is neither initiative nor slice."""
    match node.kind:
        case NodeKind.INITIATIVE:
            return TargetKind.INITIATIVE
        case NodeKind.SLICE:
            return TargetKind.SLICE
        case _:
            return None


def interpret(
    message: Message, tree: LifecycleTree, current_row: DesiredState | None
) -> Interpretation:
    """Decide what an intent does. Order: body, target linked, target kind."""
    try:
        body = IntentBody.model_validate(message.payload)
    except ValidationError as error:
        # The PM's body is untrusted input; a bad one is an answer, not a fault.
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        detail = f"{where}: {first['msg']}" if where else str(first["msg"])
        return _rejected(IntentRejection.MALFORMED_BODY, detail)

    if message.node_id is not None:
        node = tree.node(message.node_id)
        # The store guarantees the node exists; one the tree lacks has no link.
        if node is None or not tree.is_linked(node):
            return _rejected(
                IntentRejection.TARGET_UNLINKED,
                f"node {message.node_id} is not linked to Context Forge",
            )
        target_kind = _target_kind(node)
        if target_kind is None:
            return _rejected(
                IntentRejection.TARGET_NOT_INITIATIVE_OR_SLICE,
                f"node {message.node_id} is not an initiative or slice",
            )
    change = merge_intent(body, message.node_id, current_row)
    if change is None:
        return Interpretation(AcknowledgmentOutcome.NO_OP)
    return Interpretation(AcknowledgmentOutcome.APPLIED, desired_state=change)


def apply_pending_intents(store: Store, project_id: str) -> int:
    """Acknowledge every pending intent in ``seq`` order; return how many (D9).

    Store-only: it reads no link state and checks no budget. Each intent is
    acknowledged once, in its own transaction, together with its row change, so a
    crash leaves it pending and the next call applies it exactly once. Store
    failures propagate to the tenant (122, D8).
    """
    pending = store.pending_intents(project_id)
    if not pending:
        return 0
    tree = LifecycleTree(store.nodes_for_project(project_id))
    for intent in pending:
        # Read after the previous intent's write, so same-target intents compose.
        row = store.desired_state(project_id, node_id=intent.node_id)
        result = interpret(intent, tree, row)
        store.acknowledge_message(
            intent.id,
            acknowledged_by=RUNNER_ACTOR,
            outcome=result.outcome,
            reason=result.reason,
            desired_state=result.desired_state,
        )
    return len(pending)
