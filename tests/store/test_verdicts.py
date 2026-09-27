"""record_verdict: every check, the retry rule, and the round trip."""

from __future__ import annotations

import dataclasses
import logging

import pytest
from evidence_harness import (
    PROJECT,
    finding,
    provider_failure,
    seed_node,
    verdict_input,
)

from amoeba.store import (
    CommandKind,
    FindingSeverity,
    NodeNotFoundError,
    ReviewVerdict,
    Store,
    VerdictInput,
)
from amoeba.store.finding_identity import (
    RULE_VERSION,
    finding_identity,
    normalize_location,
    normalize_summary,
)

_FINDINGS = (
    finding("Second `thing` is wrong.", "src/b.py:40"),
    finding("First thing", "src/a.py#L12", FindingSeverity.NOTE),
)


def _table_counts(store: Store) -> tuple[int, int]:
    verdicts = store.verdicts(PROJECT)
    observations = sum(len(store.observations(v.id)) for v in verdicts)
    return len(verdicts), observations


def test_records_a_verdict_with_its_findings_in_order(store: Store) -> None:
    node = seed_node(store)
    record = store.record_verdict(
        verdict_input("v1", node, *_FINDINGS), project_id=PROJECT
    )

    assert record.id == "v1"
    assert record.project_id == PROJECT
    assert record.findings == _FINDINGS
    observations = store.observations("v1")
    assert [o.ordinal for o in observations] == [0, 1]
    for observation, given in zip(observations, _FINDINGS, strict=True):
        assert observation.summary == given.summary
        assert observation.location == given.location
        assert observation.normalized_summary == normalize_summary(given.summary)
        assert observation.normalized_location == normalize_location(given.location)
        assert observation.identity == finding_identity(given.location, given.summary)
        assert observation.identity_version == RULE_VERSION


def _journal_entry_on(store: Store, node_id: str) -> str:
    return store.journal_issue(
        node_id, kind=CommandKind.SQ_RUN, parameters={"pipeline": "p", "params": {}}
    ).id


def test_unknown_node_raises_and_writes_nothing(store: Store) -> None:
    seed_node(store)
    with pytest.raises(NodeNotFoundError):
        store.record_verdict(verdict_input("v1", "no-such-node"), project_id=PROJECT)
    assert _table_counts(store) == (0, 0)


def test_node_in_another_project_raises(store: Store) -> None:
    node = seed_node(store, project_id="other")
    with pytest.raises(NodeNotFoundError):
        store.record_verdict(verdict_input("v1", node), project_id=PROJECT)
    assert store.verdict("v1") is None


def test_journal_entry_on_another_node_raises(store: Store) -> None:
    node, other = seed_node(store), seed_node(store)
    entry = _journal_entry_on(store, other)
    with pytest.raises(ValueError, match="journal entry"):
        store.record_verdict(
            verdict_input("v1", node, journal_entry_id=entry), project_id=PROJECT
        )
    assert store.verdict("v1") is None


def test_unknown_journal_entry_raises(store: Store) -> None:
    node = seed_node(store)
    with pytest.raises(ValueError, match="journal entry"):
        store.record_verdict(
            verdict_input("v1", node, journal_entry_id="nope"), project_id=PROJECT
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"findings": (finding("x"),)}, "cannot carry findings"),
        ({"verdict": ReviewVerdict.CONCERNS}, "must have verdict UNKNOWN"),
    ],
)
def test_malformed_provider_failure_raises_and_writes_nothing(
    store: Store, overrides: dict[str, object], message: str
) -> None:
    node = seed_node(store)
    bad = dataclasses.replace(provider_failure("v1", node), **overrides)  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match=message):
        store.record_verdict(bad, project_id=PROJECT)
    assert _table_counts(store) == (0, 0)


@pytest.mark.parametrize("version", ["", "   "])
def test_empty_upstream_version_raises(store: Store, version: str) -> None:
    node = seed_node(store)
    base = verdict_input("v1", node, *_FINDINGS)
    bad = dataclasses.replace(
        base,
        provenance=dataclasses.replace(base.provenance, upstream_version=version),
    )
    with pytest.raises(ValueError, match="upstream_version"):
        store.record_verdict(bad, project_id=PROJECT)
    assert _table_counts(store) == (0, 0)


def test_a_valid_provider_failure_records(store: Store) -> None:
    node = seed_node(store)
    record = store.record_verdict(provider_failure("v1", node), project_id=PROJECT)
    assert record.provider_failure is True
    assert record.findings == ()


def test_retry_with_same_content_returns_the_record_silently(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    node = seed_node(store)
    first = store.record_verdict(
        verdict_input("v1", node, *_FINDINGS), project_id=PROJECT
    )
    with caplog.at_level(logging.WARNING):
        again = store.record_verdict(
            verdict_input("v1", node, *_FINDINGS), project_id=PROJECT
        )
    assert again == first
    assert caplog.records == []
    assert _table_counts(store) == (1, 2)


def test_retry_with_different_content_keeps_the_first_and_warns(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    node = seed_node(store)
    first = store.record_verdict(
        verdict_input("v1", node, *_FINDINGS), project_id=PROJECT
    )
    with caplog.at_level(logging.WARNING):
        again = store.record_verdict(
            verdict_input("v1", node, verdict=ReviewVerdict.PASS), project_id=PROJECT
        )
    assert again == first
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    assert "v1" in caplog.records[0].getMessage()
    assert _table_counts(store) == (1, 2)


def test_recorded_seq_follows_arrival_order(store: Store) -> None:
    node = seed_node(store)
    seqs = [
        store.record_verdict(verdict_input(vid, node), project_id=PROJECT).recorded_seq
        for vid in ("z", "a", "m")
    ]
    assert seqs == sorted(seqs)
    assert [v.id for v in store.verdicts(PROJECT)] == ["z", "a", "m"]


def _every_optional_field_set(node: str, entry: str) -> VerdictInput:
    base = verdict_input("v1", node, *_FINDINGS)
    return dataclasses.replace(
        base,
        score=82.5,
        criteria={"coverage": "high", "weights": [1, 2]},
        tool_calls_made=12,
        sq_run_id="run-1",
        journal_entry_id=entry,
        requested_model="glmflash",
        reviewed_sha="abc123",
        diff_truncated=True,
        fallback_used=False,
        provenance=dataclasses.replace(base.provenance, source_path="r.md"),
    )


def test_every_optional_field_round_trips_when_set(store: Store) -> None:
    node = seed_node(store)
    given = _every_optional_field_set(node, _journal_entry_on(store, node))
    store.record_verdict(given, project_id=PROJECT)

    recorded = store.verdict("v1")
    assert recorded is not None
    for name in (
        "score",
        "criteria",
        "tool_calls_made",
        "sq_run_id",
        "journal_entry_id",
        "requested_model",
        "reviewed_sha",
        "diff_truncated",
        "fallback_used",
        "provenance",
        "findings",
    ):
        assert getattr(recorded, name) == getattr(given, name), name


def test_every_optional_field_round_trips_as_none(store: Store) -> None:
    node = seed_node(store)
    store.record_verdict(
        verdict_input("v1", node, findings_parsed=None), project_id=PROJECT
    )

    recorded = store.verdict("v1")
    assert recorded is not None
    for name in (
        "score",
        "criteria",
        "tool_calls_made",
        "sq_run_id",
        "journal_entry_id",
        "requested_model",
        "reviewed_sha",
        "diff_truncated",
        "fallback_used",
        "findings_parsed",
    ):
        assert getattr(recorded, name) is None, name
    assert recorded.provenance.source_path is None
