"""Tests for the closed vocabularies and transfer objects."""

from __future__ import annotations

import pytest

from amoeba.store.models import (
    BLOCKED_KIND_TO_STATUS,
    BLOCKED_STATUSES,
    BlockedKind,
    BlockedState,
    CFReference,
    Node,
    NodeKind,
    NodeStatus,
    Resolution,
    SQReference,
)

EXPECTED_STATUS_VALUES = {
    NodeStatus.RUNNABLE: "runnable",
    NodeStatus.IN_PROGRESS: "in_progress",
    NodeStatus.BLOCKED_ON_HUMAN: "blocked_on_human",
    NodeStatus.BLOCKED_ON_JUDGE: "blocked_on_judge",
    NodeStatus.BLOCKED_ON_SQ_CHECKPOINT: "blocked_on_sq_checkpoint",
    NodeStatus.DONE: "done",
}


@pytest.mark.parametrize(
    ("status", "expected"),
    list(EXPECTED_STATUS_VALUES.items()),
    ids=lambda arg: str(arg),
)
def test_status_values_are_the_expected_readable_strings(
    status: NodeStatus, expected: str
) -> None:
    """Each member's stored value is the readable string the schema expects."""
    assert status.value == expected
    assert status == expected


def test_status_vocabulary_is_exactly_the_six_values() -> None:
    """The vocabulary is closed — no member was added without updating the test."""
    assert set(NodeStatus) == set(EXPECTED_STATUS_VALUES)


@pytest.mark.parametrize("status", list(NodeStatus), ids=lambda arg: str(arg))
def test_node_round_trips_every_status(status: NodeStatus) -> None:
    """A node constructed with any vocabulary status keeps that status."""
    node = Node(
        id="n1",
        project_id="demo",
        kind=NodeKind.SLICE,
        status=status,
        title="a slice",
    )

    assert node.status is status


@pytest.mark.parametrize(
    "unknown", ["", "RUNNABLE", "blocked", "waiting_on_human", "complete"]
)
def test_unknown_status_raises_rather_than_defaulting(unknown: str) -> None:
    """An out-of-vocabulary string raises — unknown is a value, not a default."""
    with pytest.raises(ValueError):
        NodeStatus(unknown)


@pytest.mark.parametrize("unknown", ["", "task", "phase", "SLICE"])
def test_unknown_node_kind_raises(unknown: str) -> None:
    """The node-kind vocabulary is closed on the same terms as status."""
    with pytest.raises(ValueError):
        NodeKind(unknown)


@pytest.mark.parametrize("unknown", ["", "person", "HUMAN", "pm"])
def test_unknown_blocked_kind_raises(unknown: str) -> None:
    """The blocker vocabulary is closed on the same terms as status."""
    with pytest.raises(ValueError):
        BlockedKind(unknown)


def test_blocked_statuses_are_exactly_the_blocked_on_members() -> None:
    """The blocked set is derived from the vocabulary, not a hand-kept list."""
    assert BLOCKED_STATUSES == {
        status for status in NodeStatus if status.value.startswith("blocked_on_")
    }


def test_every_blocker_kind_maps_to_a_blocked_status() -> None:
    """Each blocker kind has exactly one status, and the mapping is total."""
    assert set(BLOCKED_KIND_TO_STATUS) == set(BlockedKind)
    assert set(BLOCKED_KIND_TO_STATUS.values()) == BLOCKED_STATUSES


def test_node_attributes_round_trip() -> None:
    """Every attribute survives construction, references included."""
    cf = CFReference(
        project="amoeba",
        phase="6",
        slice_name="store-foundation-and-node-model",
        artifact_path="project-documents/user/slices/101.md",
    )
    sq = SQReference(
        run_id="run-20260917-store-abcd1234",
        review_artifact_path="project-documents/user/reviews/101-review.md",
        reviewed_sha="9fd07d4",
    )

    node = Node(
        id="n1",
        project_id="demo",
        kind=NodeKind.GATE,
        status=NodeStatus.RUNNABLE,
        title="design review",
        parent_id="n0",
        cf=cf,
        sq=sq,
    )

    assert node.parent_id == "n0"
    assert node.cf.artifact_path == "project-documents/user/slices/101.md"
    assert node.sq.run_id == "run-20260917-store-abcd1234"


def test_node_defaults_carry_empty_references() -> None:
    """A node without references still has reference objects, not None."""
    node = Node(
        id="n1",
        project_id="demo",
        kind=NodeKind.INITIATIVE,
        status=NodeStatus.RUNNABLE,
        title="substrate",
    )

    assert node.cf == CFReference()
    assert node.sq == SQReference()
    assert node.parent_id is None


def test_reference_defaults_are_not_shared_between_nodes() -> None:
    """Each node gets its own reference objects, not one shared instance."""
    first = Node(
        id="n1",
        project_id="demo",
        kind=NodeKind.SLICE,
        status=NodeStatus.RUNNABLE,
        title="one",
    )
    second = Node(
        id="n2",
        project_id="demo",
        kind=NodeKind.SLICE,
        status=NodeStatus.RUNNABLE,
        title="two",
    )

    assert first.cf is not second.cf


def test_unfilled_resolution_slot_reads_as_unresolved() -> None:
    """An unfilled slot is the checkpoint — the blocked state is not resolved."""
    blocked = BlockedState(
        id="b1",
        node_id="n1",
        kind=BlockedKind.HUMAN,
        context="awaiting PM ruling on scope",
    )

    assert blocked.resolution is None
    assert not blocked.is_resolved


def test_filled_resolution_slot_carries_its_provenance() -> None:
    """A filled slot records who resolved it and what they said."""
    blocked = BlockedState(
        id="b1",
        node_id="n1",
        kind=BlockedKind.HUMAN,
        context="awaiting PM ruling on scope",
        resolution=Resolution(resolved_by="pm", detail="add the task to 101"),
    )

    assert blocked.is_resolved
    assert blocked.resolution is not None
    assert blocked.resolution.resolved_by == "pm"
