"""Judge samples: a verdict record carrying ``judge_invocation_id`` (107, D1, D2)."""

from __future__ import annotations

from evidence_harness import PROJECT, seed_node, verdict_input
from review_fixtures import ROUND_1_PART_1

from amoeba.store import Store
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
