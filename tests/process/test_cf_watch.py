"""``CFWatchTenant``: recording moves, ignoring noise, cadence, and restart."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cf_fixture import (
    AMOEBA_ID,
    DEFAULT_WORKTREE_ID,
    OTHER_ID,
    derived,
    entry,
    fixture_bytes,
)
from cf_watch_harness import LABEL, CFRig
from feed_harness import raw_changes

from amoeba.store import CFSnapshotOutcome, Change, ChangeKind

PROJECT = "demo"


def _default_worktree(amoeba: dict[str, Any]) -> dict[str, Any]:
    return next(wt for wt in amoeba["worktrees"] if wt["id"] == DEFAULT_WORKTREE_ID)


def _moved(phase: str = "Phase 7: Testing") -> bytes:
    return derived(
        lambda es: _default_worktree(entry(es, AMOEBA_ID)).update(
            developmentPhase=phase
        )
    )


def _cf_changes(rig: CFRig, project_id: str = PROJECT) -> list[Change]:
    store = rig.host.open_project(project_id)
    return [
        change
        for change in raw_changes(store, project_id)
        if change.kind is ChangeKind.CF_PROJECT_CHANGED
    ]


def test_the_first_check_records_every_present_field_as_added(cf_rig: CFRig) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)

    assert cf_rig.tick() is True

    [snapshot] = cf_rig.snapshots()
    assert snapshot.outcome is CFSnapshotOutcome.OBSERVED
    assert snapshot.cf_version_label == LABEL
    assert snapshot.cf_updated_at is not None
    assert snapshot.changed is not None
    assert all("from" not in change for change in snapshot.changed)
    added = {(c["worktree_id"], c["field"]): c["to"] for c in snapshot.changed}
    assert added[(DEFAULT_WORKTREE_ID, "activeSlice")] == (
        "108-slice.context-forge-event-seam"
    )
    assert len(_cf_changes(cf_rig)) == 1


def test_moving_a_worktree_pointer_records_exactly_one_snapshot(cf_rig: CFRig) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)
    cf_rig.tick()

    cf_rig.write(_moved())
    assert cf_rig.tick() is True

    snapshots = cf_rig.snapshots()
    assert len(snapshots) == 2
    assert snapshots[1].changed == [
        {
            "worktree_id": DEFAULT_WORKTREE_ID,
            "field": "developmentPhase",
            "from": "Phase 6: Implementation",
            "to": "Phase 7: Testing",
        }
    ]
    assert len(_cf_changes(cf_rig)) == 2


def test_a_project_level_change_has_no_worktree_id(cf_rig: CFRig) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)
    cf_rig.tick()

    cf_rig.write(derived(lambda es: entry(es, AMOEBA_ID).update(instruction="up")))
    cf_rig.tick()

    [change] = cf_rig.snapshots()[1].changed or []
    assert change["worktree_id"] is None
    assert (change["field"], change["from"], change["to"]) == ("instruction", "", "up")


def _touch_other_project(entries: list[dict[str, Any]]) -> None:
    entry(entries, OTHER_ID).update(instruction="elsewhere")


def _touch_custom_data(entries: list[dict[str, Any]]) -> None:
    entry(entries, AMOEBA_ID).update(customData={"a": 1})


def _touch_updated_at(entries: list[dict[str, Any]]) -> None:
    entry(entries, AMOEBA_ID).update(updatedAt="2099-01-01T00:00:00Z")


@pytest.mark.parametrize(
    "noise",
    [
        pytest.param(_touch_other_project, id="another-project"),
        pytest.param(_touch_custom_data, id="custom-data"),
        pytest.param(_touch_updated_at, id="updated-at"),
    ],
)
def test_writes_that_do_not_touch_the_projection_record_nothing(
    cf_rig: CFRig, noise: Callable[[list[dict[str, Any]]], object]
) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)
    cf_rig.tick()

    cf_rig.write(derived(noise))

    assert cf_rig.tick() is False
    assert len(cf_rig.snapshots()) == 1


def test_a_tick_inside_the_interval_does_nothing_until_it_passes(cf_rig: CFRig) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)
    cf_rig.tick()
    cf_rig.write(_moved())

    cf_rig.clock.now += cf_rig.interval / 2
    assert cf_rig.tenant.tick(cf_rig.host) is False
    assert len(cf_rig.snapshots()) == 1

    cf_rig.clock.now += cf_rig.interval
    assert cf_rig.tenant.tick(cf_rig.host) is True
    assert len(cf_rig.snapshots()) == 2


def test_an_unchanged_file_and_link_set_is_one_stat_and_nothing_else(
    cf_rig: CFRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)
    cf_rig.tick()
    reads: list[Path] = []
    original = Path.read_bytes

    def counting(self: Path) -> bytes:
        reads.append(self)
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", counting)

    for _ in range(3):
        assert cf_rig.tick() is False

    assert reads == []
    assert len(cf_rig.snapshots()) == 1


def test_a_new_link_is_checked_even_when_the_file_has_not_changed(
    cf_rig: CFRig,
) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)
    cf_rig.tick()

    cf_rig.link(OTHER_ID)

    assert cf_rig.tick() is True
    assert [s.cf_project_id for s in cf_rig.snapshots()] == [AMOEBA_ID, OTHER_ID]


def test_a_recheck_of_an_unchanged_link_writes_nothing(cf_rig: CFRig) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)
    cf_rig.tick()

    cf_rig.write(fixture_bytes())  # a new inode, the same content

    assert cf_rig.tick() is False
    assert len(cf_rig.snapshots()) == 1


def test_two_amoeba_projects_linking_one_cf_project_each_record_their_own(
    cf_rig: CFRig,
) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID, "demo")
    cf_rig.link(AMOEBA_ID, "other")

    cf_rig.tick()
    cf_rig.write(_moved())
    cf_rig.tick()

    for project in ("demo", "other"):
        assert len(cf_rig.snapshots(project)) == 2
        assert len(_cf_changes(cf_rig, project)) == 2


def test_a_restart_after_a_change_while_down_records_one_per_link(
    cf_rig: CFRig,
) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)
    cf_rig.link(OTHER_ID)
    cf_rig.tick()
    before = len(cf_rig.snapshots())

    cf_rig.write(_moved())  # while "down"
    restarted = cf_rig.new_tenant()

    assert cf_rig.tick(restarted) is True
    assert len(cf_rig.snapshots()) == before + 1  # only the amoeba link moved
    assert cf_rig.snapshots()[-1].cf_project_id == AMOEBA_ID


def test_a_restart_with_nothing_changed_records_nothing(cf_rig: CFRig) -> None:
    cf_rig.write()
    cf_rig.link(AMOEBA_ID)
    cf_rig.tick()
    before = cf_rig.snapshots()

    assert cf_rig.tick(cf_rig.new_tenant()) is False
    assert cf_rig.snapshots() == before


def test_a_project_with_no_links_costs_nothing(cf_rig: CFRig) -> None:
    assert cf_rig.tick() is False
    assert cf_rig.snapshots() == []
