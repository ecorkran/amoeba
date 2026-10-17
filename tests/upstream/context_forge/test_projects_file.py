"""``parse``: the rules of the LLD D4 table, on the real fixture."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest
from cf_fixture import (
    AMOEBA_ID,
    DEFAULT_WORKTREE_ID,
    NO_WORKTREES_ID,
    OTHER_ID,
    derived,
    entry,
    fixture_bytes,
)

from amoeba.upstream.context_forge import (
    CFProjectState,
    CFReadFailure,
    CFReadOutcome,
    parse,
)


def _state(data: bytes, cf_id: str = AMOEBA_ID) -> CFProjectState:
    result = parse(data, cf_id)
    assert isinstance(result, CFProjectState), result
    return result


def _failure(data: bytes, cf_id: str = AMOEBA_ID) -> CFReadFailure:
    result = parse(data, cf_id)
    assert isinstance(result, CFReadFailure), result
    return result


def test_the_amoeba_entry_parses_with_its_default_worktree() -> None:
    state = _state(fixture_bytes())
    assert state.project["name"] == "amoeba"
    default = state.worktrees[DEFAULT_WORKTREE_ID]
    assert default["activeSlice"] == "108-slice.context-forge-event-seam"
    assert default["indexRange"] == [100, 799]
    assert default["developmentPhase"] == "Phase 6: Implementation"


def test_an_entry_without_worktrees_has_an_empty_worktree_map() -> None:
    state = _state(fixture_bytes(), NO_WORKTREES_ID)
    assert state.worktrees == {}
    assert state.project["fileSlice"] == "120-slice.setup-ide-behavior-tests"


def test_only_projected_keys_are_kept() -> None:
    state = _state(fixture_bytes())
    for unprojected in ("id", "template", "customData", "createdAt", "updatedAt"):
        assert unprojected not in state.project
    assert "isDefault" not in state.worktrees[DEFAULT_WORKTREE_ID]


def test_cf_updated_at_is_copied_when_a_string() -> None:
    assert _state(fixture_bytes()).cf_updated_at is not None
    no_stamp = derived(lambda es: entry(es, AMOEBA_ID).pop("updatedAt"))
    assert _state(no_stamp).cf_updated_at is None


def test_an_unknown_id_is_missing() -> None:
    failure = _failure(fixture_bytes(), "project_nope")
    assert failure.outcome is CFReadOutcome.MISSING
    assert "project_nope" in failure.detail


def _non_json() -> bytes:
    return fixture_bytes()[:-20]


def _top_level_object() -> bytes:
    return b'{"id": "x"}'


def _element_without_id() -> bytes:
    return derived(lambda es: entry(es, OTHER_ID).pop("id"))


def _duplicated_id() -> bytes:
    return derived(lambda es: es.append(copy.deepcopy(entry(es, AMOEBA_ID))))


def _worktrees_not_array() -> bytes:
    return derived(lambda es: entry(es, AMOEBA_ID).update(worktrees={"id": "wt_x"}))


def _worktrees_hold_non_object() -> bytes:
    return derived(lambda es: entry(es, AMOEBA_ID)["worktrees"].append("wt_x"))


def _duplicate_worktree_ids() -> bytes:
    def edit(entries: list[dict[str, Any]]) -> None:
        worktrees = entry(entries, AMOEBA_ID)["worktrees"]
        worktrees.append(copy.deepcopy(worktrees[0]))

    return derived(edit)


# Each case is one stated edit of the fixture bytes and a distinguishing detail.
DEFECTS = [
    pytest.param(_non_json, "not valid JSON", id="truncated-file-is-not-json"),
    pytest.param(lambda: b"", "not valid JSON", id="empty-file"),
    pytest.param(lambda: b"\xff\xfe", "not valid JSON", id="not-even-utf8"),
    pytest.param(_top_level_object, "top level is not an array", id="top-level-object"),
    pytest.param(_element_without_id, "string id", id="element-without-id"),
    pytest.param(_duplicated_id, "more than once", id="linked-id-duplicated"),
    pytest.param(_worktrees_not_array, "not an array", id="worktrees-not-array"),
    pytest.param(
        _worktrees_hold_non_object,
        "worktree is not an object",
        id="worktree-not-object",
    ),
    pytest.param(_duplicate_worktree_ids, "worktree id", id="duplicate-worktree-ids"),
]


@pytest.mark.parametrize(("make", "detail"), DEFECTS)
def test_defects_are_unrecognized_with_a_specific_detail(
    make: Callable[[], bytes], detail: str
) -> None:
    failure = _failure(make())
    assert failure.outcome is CFReadOutcome.UNRECOGNIZED
    assert detail in failure.detail


def test_a_file_level_defect_fails_every_link() -> None:
    data = _top_level_object()
    assert _failure(data, AMOEBA_ID) == _failure(data, NO_WORKTREES_ID)


def test_the_same_worktree_defect_in_another_entry_leaves_the_link_observed() -> None:
    def break_other(entries: list[dict[str, Any]]) -> None:
        entry(entries, OTHER_ID)["worktrees"] = {"id": "wt_x"}

    data = derived(break_other)
    assert isinstance(parse(data, AMOEBA_ID), CFProjectState)
    assert _failure(data, OTHER_ID).outcome is CFReadOutcome.UNRECOGNIZED


def test_a_changed_custom_data_or_updated_at_alone_gives_an_equal_projection() -> None:
    def touch_unprojected(entries: list[dict[str, Any]]) -> None:
        amoeba = entry(entries, AMOEBA_ID)
        amoeba["customData"] = {"note": "free text"}
        amoeba["updatedAt"] = "2099-01-01T00:00:00.000Z"

    before = _state(fixture_bytes())
    after = _state(derived(touch_unprojected))
    assert after.project == before.project
    assert after.worktrees == before.worktrees
    assert after.cf_updated_at == "2099-01-01T00:00:00.000Z"


def test_to_json_round_trips_and_rejects_other_shapes() -> None:
    state = _state(fixture_bytes())
    stored = state.to_json()
    assert set(stored) == {"project", "worktrees"}
    assert CFProjectState.from_json(stored, state.cf_updated_at) == state
    with pytest.raises(ValueError, match="objects"):
        CFProjectState.from_json({"project": {}}, None)
    with pytest.raises(ValueError, match="not an object"):
        CFProjectState.from_json({"project": {}, "worktrees": {"wt": 1}}, None)


FILE_WIDE = [_non_json, _top_level_object, _element_without_id]
LINK_ONLY = [_duplicated_id, _worktrees_not_array, _duplicate_worktree_ids]


@pytest.mark.parametrize("make", FILE_WIDE)
def test_file_level_defects_are_file_wide(make: Callable[[], bytes]) -> None:
    assert _failure(make()).file_wide is True


@pytest.mark.parametrize("make", LINK_ONLY)
def test_defects_in_the_linked_entry_are_not_file_wide(
    make: Callable[[], bytes],
) -> None:
    assert _failure(make()).file_wide is False


def test_a_missing_id_is_not_file_wide() -> None:
    assert _failure(fixture_bytes(), "project_nope").file_wide is False
