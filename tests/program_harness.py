"""Builders and helpers for program store tests: payloads, applying, snapshots."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amoeba.store.program_models import (
    ProgramSubmissionKind,
    ProgramSubmissionRecord,
)
from amoeba.store.program_store import ProgramStore

SUBMITTED_AT = datetime(2026, 11, 5, tzinfo=UTC)
CLOCK_START = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def member(
    project_id: str,
    *,
    initiative: int = 790,
    consumed: str = "from_source",
    overrides: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """One member object, shaped as the payload carries it."""
    return {
        "project_id": project_id,
        "requests_initiative": initiative,
        "consumed": consumed,
        "overrides": dict(overrides or {}),
    }


def program_payload(
    *,
    program_id: str = "demo",
    concept_member: str = "data",
    concept_path: str = "docs/concept.md",
    members: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """A ``register_program`` body; members default to ``data`` and ``engine``."""
    return {
        "program_id": program_id,
        "concept_member": concept_member,
        "concept_path": concept_path,
        "members": members
        if members is not None
        else [member("data"), member("engine")],
    }


def member_payload(
    new_member: dict[str, object], *, program_id: str = "demo"
) -> dict[str, object]:
    """A ``register_member`` body."""
    return {"program_id": program_id, "member": new_member}


def register_program(
    store: ProgramStore,
    payload: dict[str, object] | None = None,
    *,
    submission_id: str | None = None,
) -> ProgramSubmissionRecord:
    return apply(
        store,
        ProgramSubmissionKind.REGISTER_PROGRAM,
        payload if payload is not None else program_payload(),
        submission_id=submission_id,
    )


def register_member(
    store: ProgramStore,
    new_member: dict[str, object],
    *,
    program_id: str = "demo",
    submission_id: str | None = None,
) -> ProgramSubmissionRecord:
    return apply(
        store,
        ProgramSubmissionKind.REGISTER_MEMBER,
        member_payload(new_member, program_id=program_id),
        submission_id=submission_id,
    )


def apply(
    store: ProgramStore,
    kind: ProgramSubmissionKind,
    payload: dict[str, object],
    *,
    submission_id: str | None = None,
) -> ProgramSubmissionRecord:
    return store.apply_submission(
        submission_id=submission_id or uuid.uuid4().hex,
        kind=kind,
        submitted_by="tester",
        submitted_at=SUBMITTED_AT,
        payload=payload,
    )


def table_snapshot(store: ProgramStore) -> dict[str, list[tuple[object, ...]]]:
    """Every row of every table, for before/after comparisons."""
    connection = store._connection  # pyright: ignore[reportPrivateUsage]
    names = [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    return {
        name: [tuple(row) for row in connection.execute(f"SELECT * FROM {name}")]  # noqa: S608
        for name in names
    }


def without_submissions(
    snapshot: dict[str, list[tuple[object, ...]]],
) -> dict[str, list[tuple[object, ...]]]:
    """The snapshot minus the submission log, to compare what a submission wrote."""
    return {k: v for k, v in snapshot.items() if k != "program_submissions"}


def install_stepping_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the writer's clock advance one minute per call, so order is visible."""
    moments: Iterator[datetime] = (
        CLOCK_START + timedelta(minutes=step) for step in range(10_000)
    )
    monkeypatch.setattr("amoeba.store._program_writer.now", lambda: next(moments))


def open_store(tmp_path: Path) -> ProgramStore:
    return ProgramStore.open(tmp_path / "programs" / "programs.sqlite3")
