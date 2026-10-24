"""Merge one intent into a target's desired-state row (D1's table, D5).

Pure. ``None`` from ``merge_intent`` means the stored row would not change.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.runner.intent.vocabulary import IntentBody, IntentKind
from amoeba.store import ClearDesiredState, DesiredState, SetDesiredState


@dataclass(frozen=True)
class _Settings:
    """A row's three settings. ``hold`` is stored ``True`` or unset, never ``False``."""

    drive: bool | None = None
    until: str | None = None
    hold: bool | None = None


def _settings_of(row: DesiredState | None) -> _Settings:
    if row is None:
        return _Settings()
    return _Settings(row.drive, row.drive_until_step, row.hold)


def _merged(body: IntentBody, current: _Settings) -> _Settings | None:
    """The settings after the intent; ``None`` deletes the row."""
    match body.intent:
        case IntentKind.DRIVE:
            until = None if body.until is None else body.until.value
            return _Settings(True, until, current.hold)
        case IntentKind.EXCLUDE:
            return _Settings(False, None, current.hold)
        case IntentKind.PAUSE:
            return _Settings(current.drive, current.until, True)
        case IntentKind.RESUME:
            return _Settings(current.drive, current.until, None)
        case IntentKind.CLEAR:
            return None


def merge_intent(
    body: IntentBody, node_id: str | None, row: DesiredState | None
) -> SetDesiredState | ClearDesiredState | None:
    """The row change an intent makes at ``node_id``, or ``None`` for a no-op."""
    current = _settings_of(row)
    merged = _merged(body, current)
    if merged is None or (merged.drive is None and merged.hold is None):
        return None if row is None else ClearDesiredState(node_id=node_id)
    if merged == current:
        return None
    return SetDesiredState(
        node_id=node_id,
        drive=merged.drive,
        drive_until_step=merged.until,
        hold=merged.hold,
    )
