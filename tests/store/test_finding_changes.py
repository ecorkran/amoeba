"""finding_changes: every branch, and the captured 102 rounds through the store."""

from __future__ import annotations

import pytest
from evidence_harness import (
    PROJECT,
    captured_verdict,
    finding,
    provider_failure,
    seed_node,
    verdict_input,
)
from review_fixtures import ROUND_1_PART_1, ROUND_2_PART_1, ROUND_2_PART_2

from amoeba.store import (
    FindingChange,
    FindingChanges,
    Store,
    VerdictNotFoundError,
    VerdictStanding,
)

_KEPT = finding("The flag rule is unspecified", "tasks-2.md:119-163")
_KEPT_MOVED = finding("The flag rule is unspecified.", "tasks-2.md:218-240")
_DROPPED = finding("No commit checkpoint", "tasks-1.md:40")
_ADDED = finding("A brand new problem", "tasks-2.md:10")
_OTHER = finding("Some other issue", "tasks-1.md")


def _changes(changes: FindingChanges) -> list[tuple[str, FindingChange]]:
    return [(t.observation.summary, t.change) for t in changes.findings]


def test_unknown_verdict_raises(store: Store) -> None:
    with pytest.raises(VerdictNotFoundError):
        store.finding_changes("nope")


def test_first_round_has_no_previous_and_everything_is_new(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(verdict_input("r1", node, _KEPT, _DROPPED), project_id=PROJECT)

    changes = store.finding_changes("r1")
    assert changes.comparable is True
    assert changes.previous_verdict_id is None
    assert {c for _, c in _changes(changes)} == {FindingChange.NEW}
    assert changes.gone == ()


def test_moved_text_at_a_new_position_is_recurring(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(verdict_input("r1", node, _KEPT, _OTHER), project_id=PROJECT)
    store.record_verdict(
        verdict_input("r2", node, _OTHER, _KEPT_MOVED), project_id=PROJECT
    )

    changes = store.finding_changes("r2")
    assert _changes(changes) == [
        (_OTHER.summary, FindingChange.RECURRING),
        (_KEPT_MOVED.summary, FindingChange.RECURRING),
    ]


def test_round_two_tags_new_recurring_and_gone(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(verdict_input("r1", node, _KEPT, _DROPPED), project_id=PROJECT)
    store.record_verdict(
        verdict_input("r2", node, _ADDED, _KEPT_MOVED), project_id=PROJECT
    )

    changes = store.finding_changes("r2")
    assert changes.previous_verdict_id == "r1"
    assert _changes(changes) == [
        (_ADDED.summary, FindingChange.NEW),
        (_KEPT_MOVED.summary, FindingChange.RECURRING),
    ]
    assert [o.summary for o in changes.gone] == [_DROPPED.summary]


def test_a_repeated_gone_key_is_listed_once(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(
        verdict_input("r1", node, _DROPPED, _DROPPED), project_id=PROJECT
    )
    store.record_verdict(verdict_input("r2", node, _ADDED), project_id=PROJECT)
    assert len(store.finding_changes("r2").gone) == 1


def test_a_provider_failure_is_not_comparable(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(verdict_input("r1", node, _KEPT), project_id=PROJECT)
    store.record_verdict(provider_failure("r2", node), project_id=PROJECT)

    changes = store.finding_changes("r2")
    assert changes == FindingChanges(
        verdict_id="r2",
        comparable=False,
        previous_verdict_id=None,
        findings=(),
        gone=(),
    )


def test_a_provider_failure_between_rounds_is_skipped(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(verdict_input("r1", node, _KEPT), project_id=PROJECT)
    store.record_verdict(provider_failure("r2", node), project_id=PROJECT)
    store.record_verdict(verdict_input("r3", node, _KEPT_MOVED), project_id=PROJECT)

    changes = store.finding_changes("r3")
    assert changes.previous_verdict_id == "r1"
    assert _changes(changes) == [(_KEPT_MOVED.summary, FindingChange.RECURRING)]
    assert changes.gone == ()


def test_a_findings_unparsed_round_is_never_the_previous(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(verdict_input("r1", node, _KEPT), project_id=PROJECT)
    store.record_verdict(
        verdict_input("r2", node, findings_parsed=False), project_id=PROJECT
    )
    store.record_verdict(verdict_input("r3", node, _KEPT), project_id=PROJECT)

    unparsed = store.verdict("r2")
    assert unparsed is not None
    assert unparsed.standing is VerdictStanding.FINDINGS_UNPARSED
    assert store.finding_changes("r3").previous_verdict_id == "r1"
    assert store.finding_changes("r2").comparable is False


def test_another_review_type_or_node_is_never_the_previous(store: Store) -> None:
    node, other = seed_node(store), seed_node(store)
    store.record_verdict(verdict_input("r1", node, _KEPT), project_id=PROJECT)
    store.record_verdict(
        verdict_input("r2", node, _KEPT, review_type="slice"), project_id=PROJECT
    )
    store.record_verdict(verdict_input("r3", other, _KEPT), project_id=PROJECT)

    assert store.finding_changes("r2").previous_verdict_id is None
    assert store.finding_changes("r3").previous_verdict_id is None


def test_the_captured_102_rounds_through_the_store(store: Store) -> None:
    """Every finding reworded between rounds, so nothing is recurring.

    This is the rewording limit seen through ``finding_changes``: round 2 names
    round 1 as its previous round, tags every finding ``new``, and lists every
    round 1 key as ``gone``.
    """
    node = seed_node(store)
    round_1 = store.record_verdict(
        captured_verdict("round-1", node, ROUND_1_PART_1), project_id=PROJECT
    )
    round_2 = store.record_verdict(
        captured_verdict("round-2", node, ROUND_2_PART_1), project_id=PROJECT
    )
    assert round_1.standing is VerdictStanding.STATED
    assert (len(round_1.findings), len(round_2.findings)) == (9, 7)

    changes = store.finding_changes("round-2")
    assert changes.previous_verdict_id == "round-1"
    assert {c for _, c in _changes(changes)} == {FindingChange.NEW}
    assert len(changes.findings) == 7
    assert len(changes.gone) == 9


def test_the_captured_provider_failure(store: Store) -> None:
    """Round 2 part 2 is a real provider failure: UNKNOWN, no findings."""
    node = seed_node(store)
    store.record_verdict(
        captured_verdict("round-1", node, ROUND_1_PART_1), project_id=PROJECT
    )
    failure = store.record_verdict(
        captured_verdict("round-2b", node, ROUND_2_PART_2), project_id=PROJECT
    )

    assert failure.provider_failure is True
    assert failure.findings == ()
    assert failure.standing is VerdictStanding.PROVIDER_FAILURE
    assert store.finding_changes("round-2b").comparable is False
