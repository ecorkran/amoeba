"""The ``link_cf_project`` kind: its effect, its payload model, its quarantine."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from feed_harness import apply, raw_changes

from amoeba.inbox.envelope import EnvelopeError, build_envelope
from amoeba.store import QuarantineReason, Store, SubmissionKind, SubmissionOutcome
from amoeba.store.inbox_models import LINK_CF_PROJECT_ID

PROJECT = "demo"
SUBMITTED_AT = datetime(2026, 10, 16, tzinfo=UTC)


def _link(store: Store, submission_id: str, cf_id: str, project: str = PROJECT) -> None:
    record = apply(
        store,
        submission_id,
        SubmissionKind.LINK_CF_PROJECT,
        {LINK_CF_PROJECT_ID: cf_id},
        project,
    )
    assert record.outcome is SubmissionOutcome.APPLIED, record.reason


def test_the_first_submission_inserts_a_link(store: Store) -> None:
    _link(store, "s-1", "cf-1")
    [link] = store.cf_links(PROJECT)
    assert (link.project_id, link.cf_project_id) == (PROJECT, "cf-1")


def test_a_second_identical_submission_leaves_one_row(store: Store) -> None:
    _link(store, "s-1", "cf-1")
    first = store.cf_links(PROJECT)
    _link(store, "s-2", "cf-1")
    assert store.cf_links(PROJECT) == first


def test_a_replayed_submission_is_a_no_op(store: Store) -> None:
    _link(store, "s-1", "cf-1")
    before = store.cf_links(PROJECT)
    _link(store, "s-1", "cf-other")
    assert store.cf_links(PROJECT) == before


def test_two_projects_may_link_the_same_cf_project(store: Store) -> None:
    _link(store, "s-1", "cf-1", "demo")
    _link(store, "s-2", "cf-1", "other")
    assert [link.cf_project_id for link in store.cf_links("demo")] == ["cf-1"]
    assert [link.cf_project_id for link in store.cf_links("other")] == ["cf-1"]


def test_one_project_may_link_several_in_the_order_linked(store: Store) -> None:
    _link(store, "s-1", "z-first")
    _link(store, "s-2", "a-second")
    assert [link.cf_project_id for link in store.cf_links(PROJECT)] == [
        "z-first",
        "a-second",
    ]


def test_linking_emits_no_change(store: Store) -> None:
    _link(store, "s-1", "cf-1")
    assert raw_changes(store, PROJECT) == []


def test_an_empty_id_is_quarantined_as_invalid() -> None:
    with pytest.raises(EnvelopeError) as raised:
        build_envelope(
            submission_id="s-1",
            project_id=PROJECT,
            kind=SubmissionKind.LINK_CF_PROJECT,
            submitted_by="pm",
            submitted_at=SUBMITTED_AT,
            payload={LINK_CF_PROJECT_ID: ""},
        )
    assert raised.value.reason is QuarantineReason.INVALID_PAYLOAD
