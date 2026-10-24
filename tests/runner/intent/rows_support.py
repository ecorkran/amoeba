"""Hand-built desired-state rows for pure governance tests."""

from __future__ import annotations

from datetime import UTC, datetime

from amoeba.store import DesiredState, Node


def row(
    target: Node | None = None,
    *,
    drive: bool | None = None,
    until: str | None = None,
    hold: bool | None = None,
) -> DesiredState:
    """A row at ``target`` (``None`` is the project)."""
    return DesiredState(
        id=f"row-{'project' if target is None else target.id}",
        project_id="demo",
        message_id="m-0",
        updated_at=datetime(2026, 10, 23, tzinfo=UTC),
        node_id=None if target is None else target.id,
        drive=drive,
        drive_until_step=until,
        hold=hold,
    )
