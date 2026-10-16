"""The ``check`` submission kind through the envelope and ``apply_submission``.

Payloads go through ``build_envelope`` first, so the store receives exactly
what the running process hands it: the validated payload, dumped to a dict.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from evidence_harness import PROJECT, seed_node

from amoeba.inbox.envelope import EnvelopeError, build_envelope
from amoeba.store import (
    CheckOutcome,
    CheckStanding,
    QuarantineReason,
    Store,
    SubmissionKind,
    SubmissionOutcome,
    SubmissionRecord,
)

SUBMITTED_AT = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def _payload(node_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "node_id": node_id,
        "name": "cf check",
        "outcome": "passed",
        "examined_count": 12,
        "upstream": "context-forge",
        "upstream_version": "1.2.3",
        "source": "command_output",
    }
    return payload | overrides


def _submit(
    store: Store, submission_id: str, payload: Mapping[str, object]
) -> SubmissionRecord:
    envelope = build_envelope(
        submission_id=submission_id,
        project_id=PROJECT,
        kind=SubmissionKind.CHECK,
        submitted_by="ci",
        submitted_at=SUBMITTED_AT,
        payload=payload,
    )
    return store.apply_submission(
        submission_id=envelope.id,
        project_id=envelope.project_id,
        kind=envelope.kind,
        submitted_by=envelope.submitted_by,
        submitted_at=envelope.submitted_at,
        payload=envelope.payload,
    )


def test_a_valid_check_is_applied_and_readable(store: Store) -> None:
    node = seed_node(store)
    record = _submit(
        store,
        "sub-1",
        _payload(node, examined={"files": 12}, baseline_ref="abc123"),
    )

    assert record.outcome is SubmissionOutcome.APPLIED
    check = store.check("sub-1")
    assert check is not None
    assert (check.name, check.outcome) == ("cf check", CheckOutcome.PASSED)
    assert check.examined == {"files": 12}
    assert check.baseline_ref == "abc123"
    assert check.standing is CheckStanding.PASSED


def test_a_null_examined_count_is_unattested(store: Store) -> None:
    node = seed_node(store)
    _submit(store, "sub-1", _payload(node, examined_count=None))
    check = store.check("sub-1")
    assert check is not None
    assert check.standing is CheckStanding.UNATTESTED


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"examined_count": -1}, "negative"),
        ({"node_id": "no-such-node"}, "no node"),
        ({"upstream_version": ""}, "upstream_version"),
    ],
)
def test_a_failed_check_is_rejected_with_a_reason_and_writes_no_row(
    store: Store, overrides: dict[str, object], reason: str
) -> None:
    node = seed_node(store)
    record = _submit(store, "sub-1", _payload(node) | overrides)

    assert record.outcome is SubmissionOutcome.REJECTED
    assert record.reason is not None
    assert reason in record.reason
    assert store.checks(PROJECT) == []


def test_an_unknown_outcome_word_is_quarantined_at_validation(store: Store) -> None:
    with pytest.raises(EnvelopeError) as raised:
        _submit(store, "sub-1", _payload(seed_node(store), outcome="pass"))
    assert raised.value.reason is QuarantineReason.INVALID_PAYLOAD


def test_an_omitted_examined_count_fails_validation(store: Store) -> None:
    payload = _payload(seed_node(store))
    del payload["examined_count"]
    with pytest.raises(EnvelopeError) as raised:
        _submit(store, "sub-1", payload)
    assert raised.value.reason is QuarantineReason.INVALID_PAYLOAD


def test_applying_the_same_submission_again_changes_nothing(store: Store) -> None:
    node = seed_node(store)
    first = _submit(store, "sub-1", _payload(node))
    again = _submit(store, "sub-1", _payload(node, outcome="failed"))

    assert again == first
    assert [c.id for c in store.checks(PROJECT)] == ["sub-1"]
    assert len(store.submissions(PROJECT)) == 1
