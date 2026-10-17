"""``diff_states``: the rules of the LLD D3 on states parsed from the real fixture."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from cf_fixture import (
    AMOEBA_ID,
    DEFAULT_WORKTREE_ID,
    derived,
    entry,
    fixture_bytes,
)

from amoeba.upstream.context_forge import (
    ABSENT,
    CFFieldChange,
    CFProjectState,
    diff_states,
    parse,
)


def _state(data: bytes) -> CFProjectState:
    result = parse(data, AMOEBA_ID)
    assert isinstance(result, CFProjectState)
    return result


def _base() -> CFProjectState:
    return _state(fixture_bytes())


def _edited(edit: Callable[[dict[str, Any]], object]) -> CFProjectState:
    return _state(derived(lambda entries: edit(entry(entries, AMOEBA_ID))))


def _default_worktree(amoeba: dict[str, Any]) -> dict[str, Any]:
    return next(wt for wt in amoeba["worktrees"] if wt["id"] == DEFAULT_WORKTREE_ID)


def test_equal_states_give_no_changes() -> None:
    assert diff_states(_base(), _base()) == ()


def test_the_first_snapshot_lists_every_present_field_as_added() -> None:
    changes = diff_states(None, _base())
    assert all(change.before is ABSENT for change in changes)
    fields = {(change.worktree_id, change.field) for change in changes}
    assert (DEFAULT_WORKTREE_ID, "activeSlice") in fields
    assert (None, "name") in fields
    added = next(c for c in changes if c.field == "activeSlice")
    assert added.after == "108-slice.context-forge-event-seam"


def test_a_changed_value_carries_from_and_to() -> None:
    new = _edited(
        lambda a: _default_worktree(a).update(developmentPhase="Phase 7: Testing")
    )
    assert diff_states(_base(), new) == (
        CFFieldChange(
            DEFAULT_WORKTREE_ID,
            "developmentPhase",
            "Phase 6: Implementation",
            "Phase 7: Testing",
        ),
    )


def test_a_project_level_change_has_no_worktree_id() -> None:
    new = _edited(lambda a: a.update(developmentPhase="Phase 2: Planning"))
    (change,) = diff_states(_base(), new)
    assert change.worktree_id is None
    assert (change.field, change.before, change.after) == (
        "developmentPhase",
        "",
        "Phase 2: Planning",
    )


def test_a_field_added_has_no_from() -> None:
    old = _edited(lambda a: _default_worktree(a).pop("activeTaskFile"))
    (change,) = diff_states(old, _base())
    assert change.before is ABSENT
    assert change.after == "108-tasks.context-forge-event-seam"
    assert "from" not in change.to_json()


def test_a_field_removed_has_no_to() -> None:
    new = _edited(lambda a: _default_worktree(a).pop("activeTaskFile"))
    (change,) = diff_states(_base(), new)
    assert change.after is ABSENT
    assert change.before == "108-tasks.context-forge-event-seam"
    assert "to" not in change.to_json()


def test_absent_and_null_are_different() -> None:
    nulled = _edited(lambda a: _default_worktree(a).update(activeTaskFile=None))
    (change,) = diff_states(_base(), nulled)
    assert change.after is None  # null, not absent
    assert change.to_json()["to"] is None
    gone = _edited(lambda a: _default_worktree(a).pop("activeTaskFile"))
    (change,) = diff_states(nulled, gone)
    assert (change.before, change.after) == (None, ABSENT)


def test_a_worktree_added_shows_as_its_fields_added() -> None:
    def add(amoeba: dict[str, Any]) -> None:
        amoeba["worktrees"].append(
            {"id": "wt_new", "name": "feature", "activeSlice": "200-slice.x"}
        )

    changes = diff_states(_base(), _edited(add))
    assert changes == (
        CFFieldChange("wt_new", "activeSlice", ABSENT, "200-slice.x"),
        CFFieldChange("wt_new", "name", ABSENT, "feature"),
    )


def test_a_worktree_removed_shows_as_its_fields_removed() -> None:
    gone = _edited(lambda a: a["worktrees"].clear())
    changes = diff_states(_base(), gone)
    assert changes
    assert all(c.worktree_id == DEFAULT_WORKTREE_ID for c in changes)
    assert all(c.after is ABSENT and c.before is not ABSENT for c in changes)


def test_order_is_project_first_then_worktree_then_field_whatever_the_input_order() -> (
    None
):
    def scramble(amoeba: dict[str, Any]) -> None:
        amoeba["worktrees"].append({"id": "wt_a", "name": "a", "activeSlice": "s"})
        amoeba["worktrees"].reverse()
        for key in reversed(list(amoeba)):
            amoeba[key] = amoeba.pop(key)

    changes = diff_states(None, _edited(scramble))
    keys = [(c.worktree_id or "", c.field) for c in changes]
    assert keys == sorted(keys)
    assert changes[0].worktree_id is None
    assert [c.worktree_id for c in changes if c.worktree_id] == sorted(
        c.worktree_id for c in changes if c.worktree_id
    )


def test_a_change_serializes_to_the_documented_json() -> None:
    change = CFFieldChange(DEFAULT_WORKTREE_ID, "activeSlice", "a", "b")
    assert json.loads(json.dumps(change.to_json())) == {
        "worktree_id": DEFAULT_WORKTREE_ID,
        "field": "activeSlice",
        "from": "a",
        "to": "b",
    }
