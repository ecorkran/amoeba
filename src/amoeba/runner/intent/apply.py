"""Interpret an intent against the lifecycle tree (D2, D3).

``interpret`` is pure: it reads the message, the tree and the target's current row,
and answers with an outcome, a reason and the row change. Rejections are answers,
never exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from amoeba.runner.intent.merge import merge_intent
from amoeba.runner.intent.vocabulary import (
    REASON_DETAIL_LIMIT,
    IntentBody,
    IntentKind,
    IntentRejection,
    TargetKind,
    until_applies,
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
    """Decide what an intent does. Order: body, target kind, linked, ``until``."""
    try:
        body = IntentBody.model_validate(message.payload)
    except ValidationError as error:
        # The PM's body is untrusted input; a bad one is an answer, not a fault.
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        detail = f"{where}: {first['msg']}" if where else str(first["msg"])
        return _rejected(IntentRejection.MALFORMED_BODY, detail)

    kind = TargetKind.PROJECT
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
        kind = target_kind
    if (
        body.intent is IntentKind.DRIVE
        and body.until is not None
        and not until_applies(kind, body.until)
    ):
        return _rejected(
            IntentRejection.UNTIL_NOT_APPLICABLE,
            f"{body.until.value} is not a step of a {kind.value}",
        )
    change = merge_intent(body, message.node_id, current_row)
    if change is None:
        return Interpretation(AcknowledgmentOutcome.NO_OP)
    return Interpretation(AcknowledgmentOutcome.APPLIED, desired_state=change)
