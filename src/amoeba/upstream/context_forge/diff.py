"""Compare two projections of a CF project, field by field. Pure: no I/O, no store."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from amoeba.upstream.context_forge.projects_file import (
    ABSENT,
    CFFieldChange,
    CFProjectState,
)

_NOTHING = CFProjectState(project={}, worktrees={}, cf_updated_at=None)


def _scope_changes(
    worktree_id: str | None, old: Mapping[str, Any], new: Mapping[str, Any]
) -> Iterator[CFFieldChange]:
    """Changes within one scope. Absent and ``null`` differ (:data:`ABSENT`)."""
    for field in sorted(old.keys() | new.keys()):
        before = old.get(field, ABSENT)
        after = new.get(field, ABSENT)
        if before != after:
            yield CFFieldChange(worktree_id, field, before, after)


def diff_states(
    previous: CFProjectState | None, current: CFProjectState
) -> tuple[CFFieldChange, ...]:
    """What moved from ``previous`` to ``current``; ``None`` lists every field as added.

    Order is stable: project level first, then worktrees by id, then fields by name.
    A worktree that appears or vanishes shows as its fields added or removed.
    """
    before = previous or _NOTHING
    changes = list(_scope_changes(None, before.project, current.project))
    for worktree_id in sorted(before.worktrees.keys() | current.worktrees.keys()):
        changes.extend(
            _scope_changes(
                worktree_id,
                before.worktrees.get(worktree_id, {}),
                current.worktrees.get(worktree_id, {}),
            )
        )
    return tuple(changes)
