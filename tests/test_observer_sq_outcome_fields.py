"""The outcome document's ``checkpoint``, ``failure`` and ``reviews`` (slice 125, D7).

Every document here is a real ``sq runs wait --timeout 0 --json`` capture from
``tests/fixtures/sq_outcomes/`` (see the fixtures README), never one composed by
hand, so a change in Squadron's shape fails here first.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from amoeba.process import (
    OUTCOME_EXIT_CODES,
    CheckpointKind,
    FailureKind,
    PollFailure,
    RunOutcome,
    RunOutcomeDocument,
    UnknownKind,
    parse_checkpoint_kind,
    parse_failure_kind,
    poll_run,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sq_outcomes"


def _fixture(name: str) -> RunOutcomeDocument:
    return RunOutcomeDocument.model_validate_json(
        (FIXTURES / name).read_text(encoding="utf-8")
    )


def test_a_completed_run_lists_its_reviews() -> None:
    document = _fixture("completed_reviews.json")

    assert document.outcome is RunOutcome.COMPLETED
    assert document.checkpoint is None
    assert document.failure is None
    assert document.reviews is not None and len(document.reviews) == 10
    last = document.reviews[-1]
    assert last.path == (
        "project-documents/user/reviews/146-review.slice."
        "strategy-signals-markers-and-brackets.md"
    )
    assert last.paths is None
    assert (last.template, last.verdict, last.step, last.round) == (
        "slice",
        "CONCERNS",
        "slices",
        None,
    )


def test_a_split_review_carries_its_parts_in_order() -> None:
    document = _fixture("completed_split_review.json")

    assert document.reviews is not None
    assert document.reviews[-1].paths == [
        "project-documents/user/reviews/108-review.tasks.context-forge-event-seam.part-1.md",
        "project-documents/user/reviews/108-review.tasks.context-forge-event-seam.part-2.md",
    ]


def test_a_failed_run_carries_its_failure() -> None:
    document = _fixture("failed_artifact_missing.json")

    assert document.outcome is RunOutcome.FAILED
    assert document.failure is not None
    assert document.failure.kind == "artifact_missing"
    assert document.failure.step == "design-0"
    assert document.failure.message is not None
    assert document.failure.message.startswith("phase dispatch completed")
    assert parse_failure_kind(document.failure.kind) is FailureKind.ARTIFACT_MISSING
    assert document.reviews == []


def test_a_paused_run_carries_its_checkpoint() -> None:
    document = _fixture("paused_awaits_human.json")

    assert document.outcome is RunOutcome.PAUSED
    checkpoint = document.checkpoint
    assert checkpoint is not None
    assert (checkpoint.kind, checkpoint.step, checkpoint.step_type) == (
        "awaits_human",
        "branch-10",
        "branch",
    )
    assert checkpoint.is_loop is False
    assert (checkpoint.round, checkpoint.max_rounds) == (None, None)
    assert (checkpoint.verdict, checkpoint.review_file) == (None, None)
    assert checkpoint.reason == "checkpoint"
    assert checkpoint.paused_at == datetime(2026, 10, 16, 2, 20, 27, 561691, tzinfo=UTC)
    assert parse_checkpoint_kind(checkpoint.kind) is CheckpointKind.AWAITS_HUMAN


def test_a_document_without_a_reviews_key_reads_none() -> None:
    document = RunOutcomeDocument.model_validate(
        {"run_id": "run-20261022-p5-aaaa1111", "outcome": "completed"}
    )

    assert document.reviews is None
    assert document.failure is None
    assert document.checkpoint is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("loop_exhausted", CheckpointKind.LOOP_EXHAUSTED),
        ("interactive_checkpoint", CheckpointKind.INTERACTIVE_CHECKPOINT),
        ("awaits_human", CheckpointKind.AWAITS_HUMAN),
        ("other", CheckpointKind.OTHER),
        (None, None),
        ("awaits_robot", UnknownKind("awaits_robot")),
        ("Awaits_Human", UnknownKind("Awaits_Human")),
        ("", UnknownKind("")),
    ],
)
def test_checkpoint_kinds_parse_to_a_member_or_the_unknown_text(
    raw: str | None, expected: object
) -> None:
    assert parse_checkpoint_kind(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("provider_error", FailureKind.PROVIDER_ERROR),
        ("stall", FailureKind.STALL),
        ("artifact_missing", FailureKind.ARTIFACT_MISSING),
        ("cost_cap", FailureKind.COST_CAP),
        (None, None),
        ("meltdown", UnknownKind("meltdown")),
    ],
)
def test_failure_kinds_parse_to_a_member_or_the_unknown_text(
    raw: str | None, expected: object
) -> None:
    assert parse_failure_kind(raw) == expected


def test_an_unrecognized_kind_does_not_fail_a_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = (
        '{"run_id": "run-20261022-p5-aaaa1111", "outcome": "failed", '
        '"failure": {"kind": "meltdown", "step": "s", "message": "m"}}'
    )

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command, OUTCOME_EXIT_CODES[RunOutcome.FAILED], text, ""
        )

    monkeypatch.setattr("amoeba.process.sq_outcome.subprocess.run", fake_run)

    polled = poll_run("run-20261022-p5-aaaa1111", timeout_seconds=5.0)

    assert not isinstance(polled, PollFailure)
    assert polled.failure is not None
    assert parse_failure_kind(polled.failure.kind) == UnknownKind("meltdown")


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("*.json")))
def test_every_real_capture_survives_a_poll(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    document = RunOutcomeDocument.model_validate_json(text)

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command, OUTCOME_EXIT_CODES[document.outcome], text, ""
        )

    monkeypatch.setattr("amoeba.process.sq_outcome.subprocess.run", fake_run)

    assert poll_run(document.run_id, timeout_seconds=5.0) == document
