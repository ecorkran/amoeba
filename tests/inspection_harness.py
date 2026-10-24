"""A seeded supervisor directory with at least one row for every listing.

Shared by the ``inspect`` CLI tests, the migration baseline capture, and the
server parity test, so all three read the same seeded store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cf_harness import observed
from evidence_harness import check_input, finding, verdict_input
from sq_run_fixtures import sq_run_parameters

from amoeba.inbox import submit
from amoeba.store import (
    AcknowledgmentOutcome,
    BlockedKind,
    CommandKind,
    DetectionInput,
    DetectionOutcome,
    JournalOutcome,
    NodeKind,
    SetDesiredState,
    Store,
    SubmissionKind,
)
from amoeba.store.inbox_models import (
    INTENT_BODY,
    INTENT_NODE_ID,
    LINK_CF_PROJECT_ID,
    WATCH_ACTIVE,
    WATCH_REVIEWS_DIR,
)

PROJECT = "demo"

#: The review verdict ``changes`` compares against.
FIXTURE_VERDICT = "fixture-review"

#: The judge invocation the calibration sample carries.
FIXTURE_JUDGE_INVOCATION = "j1"


@dataclass(frozen=True)
class SeededStore:
    """What a listing option needs to name a seeded row."""

    project_id: str
    store_file: Path
    node_id: str
    verdict_id: str
    judge_invocation_id: str


def seed_every_listing(supervisor_dir: Path) -> SeededStore:
    """Seed one project store, plus one pending inbox file, in ``supervisor_dir``."""
    project_store_file = supervisor_dir / f"{PROJECT}.sqlite3"
    with Store.open(project_store_file) as store:
        runnable = store.create_node(
            project_id=PROJECT, kind=NodeKind.SLICE, title="runnable slice"
        )
        blocked = store.create_node(
            project_id=PROJECT, kind=NodeKind.GATE, title="awaiting review"
        )
        store.block(blocked.id, kind=BlockedKind.JUDGE, context="needs a verdict")

        resolved = store.journal_issue(
            runnable.id,
            kind=CommandKind.SQ_RUN,
            parameters=sq_run_parameters(
                {"pipeline": "p6", "params": {"slice": "102"}}
            ),
        )
        store.journal_resolve(
            resolved.id,
            outcome=JournalOutcome.COMPLETED,
            result={"run_id": "run-20260921-p6-abcd1234"},
        )
        store.journal_issue(
            runnable.id,
            kind=CommandKind.CF_WRITE,
            parameters={
                "project": "amoeba",
                "expected": {"phase": "6"},
                "checkout": "/work/amoeba",
            },
        )
        # Slice 103: a submission record and the intent message it produced.
        store.apply_submission(
            submission_id="fixture-intent",
            project_id=PROJECT,
            kind=SubmissionKind.INTENT,
            submitted_by="fixture",
            submitted_at=datetime(2026, 9, 23, tzinfo=UTC),
            payload={INTENT_NODE_ID: runnable.id, INTENT_BODY: {"want": "a run"}},
        )
        # Slice 124: one applied intent that set a desired state at the project.
        store.apply_submission(
            submission_id="fixture-desired-state",
            project_id=PROJECT,
            kind=SubmissionKind.INTENT,
            submitted_by="fixture",
            submitted_at=datetime(2026, 10, 23, tzinfo=UTC),
            payload={INTENT_NODE_ID: None, INTENT_BODY: {"intent": "pause"}},
        )
        desired_intent = store.intent_for_submission("fixture-desired-state")
        assert desired_intent is not None
        store.acknowledge_message(
            desired_intent.id,
            acknowledged_by="fixture",
            outcome=AcknowledgmentOutcome.APPLIED,
            desired_state=SetDesiredState(hold=True),
        )
        # Slice 104: one review verdict with one finding.
        store.record_verdict(
            verdict_input(FIXTURE_VERDICT, runnable.id, finding("x", "a.py:1")),
            project_id=PROJECT,
        )
        # Slice 107: one judge sample (so calibration has a row) and one check.
        store.record_verdict(
            verdict_input(
                "fixture-sample",
                runnable.id,
                judge_invocation_id=FIXTURE_JUDGE_INVOCATION,
            ),
            project_id=PROJECT,
        )
        store.record_check(
            check_input("fixture-check", runnable.id), project_id=PROJECT
        )
        # Slice 108: one Context Forge link and one observed snapshot.
        store.apply_submission(
            submission_id="fixture-cf-link",
            project_id=PROJECT,
            kind=SubmissionKind.LINK_CF_PROJECT,
            submitted_by="fixture",
            submitted_at=datetime(2026, 10, 16, tzinfo=UTC),
            payload={LINK_CF_PROJECT_ID: "fixture-cf-project"},
        )
        store.record_cf_snapshot(observed(PROJECT, "fixture-cf-project"))
        # Slice 106: one review watch and one detection ledger row.
        store.apply_submission(
            submission_id="fixture-watch",
            project_id=PROJECT,
            kind=SubmissionKind.WATCH_REVIEWS,
            submitted_by="fixture",
            submitted_at=datetime(2026, 10, 15, tzinfo=UTC),
            payload={
                WATCH_REVIEWS_DIR: str(supervisor_dir / "reviews"),
                WATCH_ACTIVE: True,
            },
        )
        store.record_detection(
            DetectionInput(
                project_id=PROJECT,
                path=str(supervisor_dir / "reviews" / "notes.md"),
                digest="fixture-digest",
                outcome=DetectionOutcome.UNPARSEABLE,
                detail="not a review",
            )
        )
    # And one file still waiting in the inbox, written by the real submit().
    submit(
        project_id=PROJECT,
        kind=SubmissionKind.INTENT,
        payload={INTENT_BODY: {"want": "later"}},
        submitted_by="fixture",
        store_dir=supervisor_dir,
    )
    return SeededStore(
        project_id=PROJECT,
        store_file=project_store_file,
        node_id=runnable.id,
        verdict_id=FIXTURE_VERDICT,
        judge_invocation_id=FIXTURE_JUDGE_INVOCATION,
    )
