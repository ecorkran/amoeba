"""Builders for Context Forge snapshot inputs, shared by store and tenant tests."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

from amoeba.store import CFSnapshotInput, CFSnapshotOutcome

OBSERVED_AT = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
VERSION_LABEL = "cf 0.19.13"


def observed(
    project_id: str, cf_project_id: str, **overrides: object
) -> CFSnapshotInput:
    """An ``observed`` snapshot with one change; ``overrides`` replace any field."""
    base = CFSnapshotInput(
        project_id=project_id,
        cf_project_id=cf_project_id,
        outcome=CFSnapshotOutcome.OBSERVED,
        state={"project": {"name": "demo"}, "worktrees": {}},
        changed=[{"worktree_id": None, "field": "name", "to": "demo"}],
        detail=None,
        cf_updated_at="2026-10-16T12:00:00.000Z",
        cf_version_label=VERSION_LABEL,
        observed_at=OBSERVED_AT,
    )
    return dataclasses.replace(base, **overrides)  # pyright: ignore[reportArgumentType]


def failure(
    project_id: str,
    cf_project_id: str,
    outcome: CFSnapshotOutcome,
    detail: str = "something specific",
) -> CFSnapshotInput:
    """A failure snapshot: no state, no changes, a detail."""
    assert outcome is not CFSnapshotOutcome.OBSERVED
    return CFSnapshotInput(
        project_id=project_id,
        cf_project_id=cf_project_id,
        outcome=outcome,
        state=None,
        changed=None,
        detail=detail,
        cf_updated_at=None,
        cf_version_label=VERSION_LABEL,
        observed_at=OBSERVED_AT,
    )
