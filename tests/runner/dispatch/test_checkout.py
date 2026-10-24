"""D1: the checkout that owns a slice, from the link's latest observed snapshot."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from cf_harness import observed

from amoeba.runner.dispatch.checkout import (
    Checkout,
    CheckoutUnresolved,
    resolve_checkout,
)
from amoeba.store import CFSnapshot, Store
from amoeba.upstream.context_forge import (
    FIELD_INDEX_RANGE,
    FIELD_PROJECT_PATH,
    FIELD_WORKTREE_PATH,
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
)

PROJECT = "demo"
CF_ID = "project_1_abc"
ROOT = Path("/work/amoeba")
SECOND = Path("/work/amoeba-2")


def _worktree(path: object, low: object, high: object) -> dict[str, object]:
    return {FIELD_WORKTREE_PATH: path, FIELD_INDEX_RANGE: [low, high]}


def _snapshot(
    store: Store,
    worktrees: dict[str, object] | None = None,
    project_path: object = str(ROOT),
) -> CFSnapshot:
    state = {
        STATE_PROJECT_KEY: {FIELD_PROJECT_PATH: project_path},
        STATE_WORKTREES_KEY: worktrees or {},
    }
    return store.record_cf_snapshot(observed(PROJECT, CF_ID, state=state, changed=[]))


def _everywhere(_: Path) -> bool:
    return True


def _only(*directories: Path) -> Callable[[Path], bool]:
    return lambda path: path in directories


def test_two_worktrees_and_the_index_in_the_second(store: Store) -> None:
    snapshot = _snapshot(
        store,
        {
            "wt_a": _worktree(str(ROOT), 100, 199),
            "wt_b": _worktree(str(SECOND), 200, 299),
        },
    )

    assert resolve_checkout(snapshot, 250, is_dir=_everywhere) == Checkout(
        SECOND, "wt_b"
    )


def test_no_worktrees_uses_the_project_path(store: Store) -> None:
    snapshot = _snapshot(store)

    assert resolve_checkout(snapshot, 125, is_dir=_everywhere) == Checkout(ROOT, None)


@pytest.mark.parametrize(
    ("index", "owner"), [(100, "wt_a"), (199, "wt_a"), (200, "wt_b")]
)
def test_range_bounds_are_inclusive_at_both_ends(
    store: Store, index: int, owner: str
) -> None:
    snapshot = _snapshot(
        store,
        {
            "wt_a": _worktree(str(ROOT), 100, 199),
            "wt_b": _worktree(str(SECOND), 200, 299),
        },
    )

    found = resolve_checkout(snapshot, index, is_dir=_everywhere)

    assert isinstance(found, Checkout) and found.worktree_id == owner


def test_no_snapshot_is_unresolved() -> None:
    found = resolve_checkout(None, 125, is_dir=_everywhere)

    assert isinstance(found, CheckoutUnresolved)
    assert "no observed snapshot" in found.reason


def test_no_range_containing_the_index_is_unresolved(store: Store) -> None:
    snapshot = _snapshot(store, {"wt_a": _worktree(str(ROOT), 100, 199)})

    found = resolve_checkout(snapshot, 500, is_dir=_everywhere)

    assert isinstance(found, CheckoutUnresolved)
    assert "no worktree's range contains index 500" in found.reason


def test_two_ranges_containing_the_index_is_unresolved(store: Store) -> None:
    snapshot = _snapshot(
        store,
        {
            "wt_a": _worktree(str(ROOT), 100, 199),
            "wt_b": _worktree(str(SECOND), 150, 250),
        },
    )

    found = resolve_checkout(snapshot, 175, is_dir=_everywhere)

    assert isinstance(found, CheckoutUnresolved)
    assert "wt_a, wt_b" in found.reason


@pytest.mark.parametrize("path", ["", None, 7])
def test_a_missing_or_empty_worktree_path_is_unresolved(
    store: Store, path: object
) -> None:
    snapshot = _snapshot(store, {"wt_a": _worktree(path, 100, 199)})

    found = resolve_checkout(snapshot, 150, is_dir=_everywhere)

    assert isinstance(found, CheckoutUnresolved)
    assert "missing or empty" in found.reason


def test_a_relative_path_is_unresolved(store: Store) -> None:
    snapshot = _snapshot(store, {"wt_a": _worktree("relative/dir", 100, 199)})

    found = resolve_checkout(snapshot, 150, is_dir=_everywhere)

    assert isinstance(found, CheckoutUnresolved)
    assert "not an absolute path" in found.reason


def test_a_path_that_is_not_a_directory_is_unresolved(store: Store) -> None:
    snapshot = _snapshot(store, {"wt_a": _worktree(str(ROOT), 100, 199)})

    found = resolve_checkout(snapshot, 150, is_dir=_only(SECOND))

    assert isinstance(found, CheckoutUnresolved)
    assert "not an existing directory" in found.reason


def test_a_project_path_that_is_not_a_directory_is_unresolved(store: Store) -> None:
    found = resolve_checkout(_snapshot(store), 150, is_dir=_only())

    assert isinstance(found, CheckoutUnresolved)
    assert "projectPath" in found.reason


@pytest.mark.parametrize(
    "bad_range", [None, [1], [1, 2, 3], ["a", "b"], [True, 5], "100-199"]
)
def test_a_malformed_range_is_unresolved(store: Store, bad_range: object) -> None:
    worktree = {FIELD_WORKTREE_PATH: str(ROOT), FIELD_INDEX_RANGE: bad_range}
    snapshot = _snapshot(store, {"wt_a": worktree})

    found = resolve_checkout(snapshot, 150, is_dir=_everywhere)

    assert isinstance(found, CheckoutUnresolved)
    assert "wt_a" in found.reason and FIELD_INDEX_RANGE in found.reason


def test_a_worktree_that_is_not_an_object_is_unresolved(store: Store) -> None:
    snapshot = _snapshot(store, {"wt_a": "oops"})

    found = resolve_checkout(snapshot, 150, is_dir=_everywhere)

    assert isinstance(found, CheckoutUnresolved)
    assert "wt_a is not an object" in found.reason
