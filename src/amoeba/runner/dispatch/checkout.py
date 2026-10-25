"""Where a slice runs: the checkout of the CF worktree that owns its index (D1).

CF picks a worktree only by working directory, so every ``cf`` and ``sq`` call for a
step must run in that worktree's path. The answer comes from the link's latest
*observed* snapshot (a store read, no subprocess) and is checked again by the
pointer write's read-back, so a stale snapshot cannot silently send a run to the
wrong tree.

Anything the snapshot does not settle is :class:`CheckoutUnresolved`; no checkout
is ever guessed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard, cast

from amoeba.store import CFSnapshot
from amoeba.upstream.context_forge import (
    FIELD_INDEX_RANGE,
    FIELD_PROJECT_PATH,
    FIELD_WORKTREE_PATH,
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
)


@dataclass(frozen=True)
class Checkout:
    """A directory to run in. ``worktree_id`` is ``None`` for a project with none."""

    path: Path
    worktree_id: str | None


@dataclass(frozen=True)
class CheckoutUnresolved:
    """No checkout can be named; ``reason`` says which case."""

    reason: str


#: A range's two inclusive bounds.
_RANGE_LENGTH = 2


def resolve_checkout(
    snapshot: CFSnapshot | None,
    slice_index: int,
    *,
    is_dir: Callable[[Path], bool],
) -> Checkout | CheckoutUnresolved:
    """The checkout that owns ``slice_index`` in ``snapshot``, or why none does.

    ``snapshot`` is the link's latest observed one. ``is_dir`` is injected so the
    function stays pure; production passes ``Path.is_dir``.
    """
    if snapshot is None or snapshot.state is None:
        return CheckoutUnresolved("no observed snapshot of the CF project")
    project = _mapping(snapshot.state.get(STATE_PROJECT_KEY))
    worktrees = _mapping(snapshot.state.get(STATE_WORKTREES_KEY))
    if project is None or worktrees is None:
        return CheckoutUnresolved("the CF snapshot has no project and worktrees")
    if not worktrees:
        return _checked(project.get(FIELD_PROJECT_PATH), None, "projectPath", is_dir)
    return _from_worktrees(worktrees, slice_index, is_dir)


def _mapping(value: object) -> Mapping[str, object] | None:
    """``value`` as a string-keyed mapping, or ``None`` if it is not one."""
    return cast("Mapping[str, object]", value) if isinstance(value, Mapping) else None


def _from_worktrees(
    worktrees: Mapping[str, object],
    slice_index: int,
    is_dir: Callable[[Path], bool],
) -> Checkout | CheckoutUnresolved:
    owners: list[tuple[str, object]] = []
    for worktree_id, raw in worktrees.items():
        fields = _mapping(raw)
        if fields is None:
            return CheckoutUnresolved(f"worktree {worktree_id} is not an object")
        bounds = _bounds(fields.get(FIELD_INDEX_RANGE))
        if bounds is None:
            return CheckoutUnresolved(
                f"worktree {worktree_id} has no usable {FIELD_INDEX_RANGE}"
            )
        if bounds[0] <= slice_index <= bounds[1]:
            owners.append((worktree_id, fields.get(FIELD_WORKTREE_PATH)))
    if not owners:
        return CheckoutUnresolved(f"no worktree's range contains index {slice_index}")
    if len(owners) > 1:
        ids = ", ".join(sorted(worktree_id for worktree_id, _ in owners))
        return CheckoutUnresolved(
            f"worktrees {ids} all contain index {slice_index}; none is chosen"
        )
    [(worktree_id, path)] = owners
    return _checked(path, worktree_id, f"worktree {worktree_id} path", is_dir)


def _bounds(value: object) -> tuple[int, int] | None:
    """A ``[low, high]`` pair of integers, or ``None`` for any other shape."""
    if not isinstance(value, list | tuple):
        return None
    pair = list(cast("list[object]", value))
    if len(pair) != _RANGE_LENGTH:
        return None
    low, high = pair
    if not (is_plain_int(low) and is_plain_int(high)):
        return None
    return low, high


def is_plain_int(value: object) -> TypeGuard[int]:
    """An integer; ``bool`` is not one, though Python says so."""
    return isinstance(value, int) and not isinstance(value, bool)


def _checked(
    path: object,
    worktree_id: str | None,
    what: str,
    is_dir: Callable[[Path], bool],
) -> Checkout | CheckoutUnresolved:
    if not isinstance(path, str) or not path:
        return CheckoutUnresolved(f"the {what} is missing or empty")
    directory = Path(path)
    if not directory.is_absolute():
        return CheckoutUnresolved(f"the {what} {path!r} is not an absolute path")
    if not is_dir(directory):
        return CheckoutUnresolved(f"the {what} {path!r} is not an existing directory")
    return Checkout(directory, worktree_id)
