"""The verdict read methods: ordering, filtering, per-key summaries, unknown ids."""

from __future__ import annotations

from pathlib import Path

import pytest
from evidence_harness import PROJECT, finding, seed_node, verdict_input

from amoeba.store import (
    FindingSeverity,
    Store,
    VerdictNotFoundError,
)


def test_unknown_verdict_id(store: Store) -> None:
    assert store.verdict("nope") is None
    with pytest.raises(VerdictNotFoundError):
        store.observations("nope")


def test_verdicts_order_by_arrival_and_filter_by_node(store: Store) -> None:
    first, second = seed_node(store), seed_node(store)
    for verdict_id, node in (("c", first), ("a", second), ("b", first)):
        store.record_verdict(verdict_input(verdict_id, node), project_id=PROJECT)

    assert [v.id for v in store.verdicts(PROJECT)] == ["c", "a", "b"]
    assert [v.id for v in store.verdicts(PROJECT, node_id=first)] == ["c", "b"]
    assert [v.id for v in store.verdicts(PROJECT, node_id=second)] == ["a"]
    assert store.verdicts("other-project") == []


def test_observations_of_a_review_without_findings_is_empty(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(verdict_input("v1", node), project_id=PROJECT)
    assert store.observations("v1") == []


def test_findings_merges_one_key_across_reviews(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(
        verdict_input("r1", node, finding("The value is wrong", "a.py:10")),
        project_id=PROJECT,
    )
    store.record_verdict(
        verdict_input(
            "r2",
            node,
            finding("The `value` is wrong.", "a.py:88", FindingSeverity.NOTE),
        ),
        project_id=PROJECT,
    )

    (row,) = store.findings(PROJECT)
    assert row.node_id == node
    assert row.times_seen == 2
    assert row.first_verdict_id == "r1"
    assert row.last_verdict_id == "r2"
    assert row.latest_severity is FindingSeverity.NOTE
    assert row.latest_summary == "The `value` is wrong."
    assert row.latest_location == "a.py:88"


def test_findings_keeps_the_same_key_on_different_nodes_apart(store: Store) -> None:
    first, second = seed_node(store), seed_node(store)
    same = finding("Same text", "a.py")
    store.record_verdict(verdict_input("r1", first, same), project_id=PROJECT)
    store.record_verdict(verdict_input("r2", second, same), project_id=PROJECT)

    rows = store.findings(PROJECT)
    assert [(r.node_id, r.times_seen) for r in rows] == [(first, 1), (second, 1)]
    assert rows[0].identity == rows[1].identity
    assert [r.node_id for r in store.findings(PROJECT, node_id=second)] == [second]


def test_a_repeated_key_in_one_review_is_two_observations_one_finding(
    store: Store,
) -> None:
    node = seed_node(store)
    store.record_verdict(
        verdict_input("r1", node, finding("Dup", "a.py:1"), finding("dup.", "a.py:9")),
        project_id=PROJECT,
    )

    observations = store.observations("r1")
    assert len(observations) == 2
    assert observations[0].identity == observations[1].identity
    (row,) = store.findings(PROJECT)
    assert row.times_seen == 1


def test_every_read_works_through_a_read_only_handle(store_file: Path) -> None:
    with Store.open(store_file) as writer:
        node = seed_node(writer)
        writer.record_verdict(
            verdict_input("r1", node, finding("x", "a.py")), project_id=PROJECT
        )

    with Store.open_read_only(store_file) as reader:
        record = reader.verdict("r1")
        assert record is not None
        assert record.findings == (finding("x", "a.py"),)
        assert [v.id for v in reader.verdicts(PROJECT)] == ["r1"]
        assert len(reader.observations("r1")) == 1
        assert len(reader.findings(PROJECT)) == 1
