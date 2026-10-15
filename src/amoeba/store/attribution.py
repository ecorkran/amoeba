"""Which slice node a review belongs to (D4 of slice 106). Pure; defined once.

A review attaches to the one node in its project with ``kind == slice`` and
``cf.slice_name`` equal to the review's frontmatter ``slice``. Zero or several
matches attach it nowhere. Review detection uses this rule, and initiative 120
must attach the reviews it launches with the same rule, or detected and
Runner-launched rounds of one slice split across two nodes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from amoeba.store.models import Node, NodeKind


@dataclass(frozen=True)
class Attribution:
    """The node a review attaches to, or ``None``, and every matching node id."""

    node_id: str | None
    candidates: tuple[str, ...]


def attribute_review(slice_nodes: Sequence[Node], slice_name: str) -> Attribution:
    """Attach a review to its slice node.

    Args:
        slice_nodes: The project's nodes. Filtered to slice nodes here, so a
            caller may pass every node in the project.
        slice_name: The review's frontmatter ``slice``.

    Returns:
        ``node_id`` set when exactly one node matches; otherwise ``None``, with
        every match in ``candidates`` (empty for none).
    """
    candidates = tuple(
        node.id
        for node in slice_nodes
        if node.kind is NodeKind.SLICE and node.cf.slice_name == slice_name
    )
    return Attribution(
        node_id=candidates[0] if len(candidates) == 1 else None,
        candidates=candidates,
    )
