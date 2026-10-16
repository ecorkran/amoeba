"""Judge samples: a verdict record carrying ``judge_invocation_id`` (107, D1, D2)."""

from __future__ import annotations

import dataclasses

import pytest
from evidence_harness import PROJECT, PROVENANCE, seed_node, verdict_input
from review_fixtures import ROUND_1_PART_1

from amoeba.store import Provenance, Store, VerdictInput
from amoeba.upstream.squadron import (
    parse_review_artifact,
    review_record_id,
    to_verdict_input,
)


def test_an_invocation_id_reads_back(store: Store) -> None:
    node = seed_node(store)
    recorded = store.record_verdict(
        verdict_input("s1", node, judge_invocation_id="j1"), project_id=PROJECT
    )
    assert recorded.judge_invocation_id == "j1"
    verdict = store.verdict("s1")
    assert verdict is not None
    assert verdict.judge_invocation_id == "j1"


def test_no_invocation_id_reads_back_as_none(store: Store) -> None:
    node = seed_node(store)
    recorded = store.record_verdict(verdict_input("v1", node), project_id=PROJECT)
    assert recorded.judge_invocation_id is None


def test_to_verdict_input_sets_the_invocation_without_changing_the_record_id() -> None:
    parsed = parse_review_artifact(ROUND_1_PART_1.read_text(encoding="utf-8"))
    plain = to_verdict_input(parsed, node_id="n-1", upstream_version="0.14.0")
    sample = to_verdict_input(
        parsed, node_id="n-1", upstream_version="0.14.0", judge_invocation_id="j1"
    )
    assert plain.judge_invocation_id is None
    assert sample.judge_invocation_id == "j1"
    assert plain.id == sample.id == review_record_id(parsed)


# --------------------------------------------------------------------------
# D2: all samples of one invocation share a node and a review type
# --------------------------------------------------------------------------


def _sample(
    sample_id: str, node_id: str, *, invocation: str = "j1", **overrides: object
) -> VerdictInput:
    return verdict_input(
        sample_id, node_id, judge_invocation_id=invocation, **overrides
    )


def test_a_second_sample_on_another_node_raises(store: Store) -> None:
    first, other = seed_node(store), seed_node(store)
    store.record_verdict(_sample("s1", first), project_id=PROJECT)
    with pytest.raises(ValueError, match="j1") as refused:
        store.record_verdict(_sample("s2", other), project_id=PROJECT)
    assert "new invocation id" in str(refused.value)
    assert first in str(refused.value)
    assert other in str(refused.value)
    assert [v.id for v in store.verdicts(PROJECT)] == ["s1"]


def test_a_second_sample_of_another_review_type_raises(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(_sample("s1", node), project_id=PROJECT)
    with pytest.raises(ValueError, match="j1") as refused:
        store.record_verdict(
            _sample("s2", node, review_type="slice"), project_id=PROJECT
        )
    assert "new invocation id" in str(refused.value)
    assert "'slice'" in str(refused.value)
    assert [v.id for v in store.verdicts(PROJECT)] == ["s1"]


def test_a_rejected_first_sample_leaves_the_invocation_undefined(
    store: Store,
) -> None:
    node, other = seed_node(store), seed_node(store)
    # Rejected by a 104 check, so it writes nothing and defines nothing.
    with pytest.raises(ValueError, match="upstream_version"):
        store.record_verdict(
            _sample("bad", node, provenance=_blank_version()), project_id=PROJECT
        )
    recorded = store.record_verdict(_sample("s1", other), project_id=PROJECT)
    assert recorded.node_id == other


def _blank_version() -> Provenance:
    return dataclasses.replace(PROVENANCE, upstream_version=" ")


def test_a_retry_of_a_recorded_sample_is_not_rechecked(store: Store) -> None:
    node, other = seed_node(store), seed_node(store)
    first = store.record_verdict(_sample("s1", node), project_id=PROJECT)
    store.record_verdict(_sample("s2", node), project_id=PROJECT)
    again = store.record_verdict(_sample("s1", node), project_id=PROJECT)
    assert again == first
    # Samples on another invocation id are a separate invocation, so also fine.
    store.record_verdict(_sample("s3", other, invocation="j2"), project_id=PROJECT)
    assert [v.id for v in store.verdicts(PROJECT)] == ["s1", "s2", "s3"]


def test_a_verdict_without_an_invocation_is_unaffected(store: Store) -> None:
    node, other = seed_node(store), seed_node(store)
    store.record_verdict(_sample("s1", node), project_id=PROJECT)
    ordinary = store.record_verdict(
        verdict_input("v1", other, review_type="slice"), project_id=PROJECT
    )
    assert ordinary.judge_invocation_id is None
