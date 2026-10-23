"""``attribute_review`` (D4) and the review-producing journal kinds (D5)."""

from __future__ import annotations

from sq_run_fixtures import sq_run_parameters

from amoeba.store import (
    CFReference,
    CommandKind,
    JournalOutcome,
    JournalResolver,
    Node,
    NodeKind,
    NodeStatus,
    Store,
    attribute_review,
)

PROJECT = "demo"
SLICE = "resident-process-and-recovery"


def _node(node_id: str, kind: NodeKind, slice_name: str | None) -> Node:
    return Node(
        id=node_id,
        project_id=PROJECT,
        kind=kind,
        status=NodeStatus.RUNNABLE,
        title=node_id,
        cf=CFReference(slice_name=slice_name),
    )


def test_one_match_attaches() -> None:
    nodes = [_node("a", NodeKind.SLICE, SLICE), _node("b", NodeKind.SLICE, "other")]
    attribution = attribute_review(nodes, SLICE)
    assert (attribution.node_id, attribution.candidates) == ("a", ("a",))


def test_zero_matches_attach_nowhere_with_no_candidates() -> None:
    attribution = attribute_review([_node("b", NodeKind.SLICE, "other")], SLICE)
    assert (attribution.node_id, attribution.candidates) == (None, ())


def test_two_matches_attach_nowhere_and_name_both() -> None:
    nodes = [_node("a", NodeKind.SLICE, SLICE), _node("b", NodeKind.SLICE, SLICE)]
    attribution = attribute_review(nodes, SLICE)
    assert (attribution.node_id, attribution.candidates) == (None, ("a", "b"))


def test_the_right_name_on_a_non_slice_node_does_not_match() -> None:
    attribution = attribute_review([_node("g", NodeKind.GATE, SLICE)], SLICE)
    assert attribution.candidates == ()


def test_a_slice_node_with_no_cf_reference_does_not_match() -> None:
    attribution = attribute_review([_node("a", NodeKind.SLICE, None)], SLICE)
    assert attribution.candidates == ()


# --------------------------------------------------------------------------
# has_unresolved_review_entry
# --------------------------------------------------------------------------

SQ_PARAMETERS: dict[str, object] = sq_run_parameters({"pipeline": "p6", "params": {}})
CF_PARAMETERS: dict[str, object] = {"project": "p", "expected": {}}


def _slice(store: Store) -> str:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s").id


def test_no_entries_is_false(store: Store) -> None:
    assert store.has_unresolved_review_entry(PROJECT) is False


def test_an_open_sq_run_is_true(store: Store) -> None:
    store.journal_issue(
        _slice(store), kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    assert store.has_unresolved_review_entry(PROJECT) is True


def test_an_open_entry_of_another_kind_is_false(store: Store) -> None:
    store.journal_issue(
        _slice(store), kind=CommandKind.CF_WRITE, parameters=CF_PARAMETERS
    )
    assert store.has_unresolved_review_entry(PROJECT) is False


def test_a_resolved_sq_run_is_false(store: Store) -> None:
    entry = store.journal_issue(
        _slice(store), kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    store.journal_resolve(
        entry.id,
        outcome=JournalOutcome.COMPLETED,
        result={},
        resolved_by=JournalResolver.ISSUER,
    )
    assert store.has_unresolved_review_entry(PROJECT) is False
