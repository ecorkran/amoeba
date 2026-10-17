"""``CFWatchTenant``: failures are outcomes, recorded once per transition."""

from __future__ import annotations

import logging
import os
import subprocess
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
from cf_watch_harness import CFRig

from amoeba.store import CFSnapshotOutcome

OUTCOMES = CFSnapshotOutcome


def _outcomes(rig: CFRig) -> list[tuple[str, CFSnapshotOutcome]]:
    return [(s.cf_project_id, s.outcome) for s in rig.snapshots()]


def _watching(rig: CFRig, *cf_ids: str) -> None:
    for cf_id in cf_ids:
        rig.link(cf_id)


def test_an_absent_file_is_unreadable_for_every_link(cf_rig: CFRig) -> None:
    _watching(cf_rig, AMOEBA_ID, OTHER_ID)

    assert cf_rig.tick() is True

    assert _outcomes(cf_rig) == [
        (AMOEBA_ID, OUTCOMES.UNREADABLE),
        (OTHER_ID, OUTCOMES.UNREADABLE),
    ]
    assert all(
        s.detail and s.detail.startswith("FileNotFoundError: ")
        for s in cf_rig.snapshots()
    )


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_a_file_that_cannot_be_read_is_unreadable_and_retried(cf_rig: CFRig) -> None:
    cf_rig.write()
    cf_rig.data_file.chmod(0o000)
    _watching(cf_rig, AMOEBA_ID)

    cf_rig.tick()
    [snapshot] = cf_rig.snapshots()
    assert snapshot.outcome is OUTCOMES.UNREADABLE
    assert (snapshot.detail or "").startswith("PermissionError: ")

    # Fixing the mode leaves the signature unchanged; the next tick still sees it.
    cf_rig.data_file.chmod(0o644)
    cf_rig.tick()
    assert [s.outcome for s in cf_rig.snapshots()] == [
        OUTCOMES.UNREADABLE,
        OUTCOMES.OBSERVED,
    ]


@pytest.mark.parametrize("content", [b"{not json", b"{}"])
def test_a_file_that_is_not_the_documented_shape_is_unrecognized(
    cf_rig: CFRig, content: bytes
) -> None:
    cf_rig.write(content)
    _watching(cf_rig, AMOEBA_ID, OTHER_ID)

    cf_rig.tick()

    assert _outcomes(cf_rig) == [
        (AMOEBA_ID, OUTCOMES.UNRECOGNIZED),
        (OTHER_ID, OUTCOMES.UNRECOGNIZED),
    ]


def test_an_unknown_id_is_missing_for_that_link_only(cf_rig: CFRig) -> None:
    cf_rig.write()
    _watching(cf_rig, AMOEBA_ID, "project_nope")

    cf_rig.tick()

    assert _outcomes(cf_rig) == [
        (AMOEBA_ID, OUTCOMES.OBSERVED),
        ("project_nope", OUTCOMES.MISSING),
    ]


def _break_worktrees(cf_id: str) -> bytes:
    return derived(lambda es: entry(es, cf_id).update(worktrees={"id": "wt"}))


def test_malformed_worktrees_in_the_linked_entry_is_unrecognized_for_it_only(
    cf_rig: CFRig,
) -> None:
    cf_rig.write(_break_worktrees(AMOEBA_ID))
    _watching(cf_rig, AMOEBA_ID, NO_WORKTREES_ID)

    cf_rig.tick()

    assert _outcomes(cf_rig) == [
        (AMOEBA_ID, OUTCOMES.UNRECOGNIZED),
        (NO_WORKTREES_ID, OUTCOMES.OBSERVED),
    ]


def test_the_same_defect_in_another_entry_leaves_the_link_observed(
    cf_rig: CFRig,
) -> None:
    cf_rig.write(_break_worktrees(OTHER_ID))
    _watching(cf_rig, AMOEBA_ID)

    cf_rig.tick()

    assert _outcomes(cf_rig) == [(AMOEBA_ID, OUTCOMES.OBSERVED)]


def test_a_file_that_stays_broken_records_one_row_per_link_not_one_per_interval(
    cf_rig: CFRig,
) -> None:
    cf_rig.write(b"{}")
    _watching(cf_rig, AMOEBA_ID, OTHER_ID)

    for _ in range(5):
        cf_rig.tick()

    assert len(cf_rig.snapshots()) == 2


def test_a_changed_detail_records_a_new_row(cf_rig: CFRig) -> None:
    cf_rig.write(b"{}")
    _watching(cf_rig, AMOEBA_ID)
    cf_rig.tick()

    cf_rig.write(b"{not json")
    cf_rig.tick()

    [first, second] = cf_rig.snapshots()
    assert first.detail != second.detail
    assert second.outcome is OUTCOMES.UNRECOGNIZED


def test_recovery_records_observed_with_no_changes_when_nothing_moved(
    cf_rig: CFRig,
) -> None:
    cf_rig.write()
    _watching(cf_rig, AMOEBA_ID)
    cf_rig.tick()
    cf_rig.write(b"{}")
    cf_rig.tick()

    cf_rig.write()  # the same content as before the breakage
    cf_rig.tick()

    assert [s.outcome for s in cf_rig.snapshots()] == [
        OUTCOMES.OBSERVED,
        OUTCOMES.UNRECOGNIZED,
        OUTCOMES.OBSERVED,
    ]
    assert cf_rig.snapshots()[-1].changed == []


def test_the_diff_after_recovery_is_against_the_last_observed_row(
    cf_rig: CFRig,
) -> None:
    cf_rig.write()
    _watching(cf_rig, AMOEBA_ID)
    cf_rig.tick()
    cf_rig.write(b"{}")
    cf_rig.tick()

    def move(entries: list[dict[str, Any]]) -> None:
        worktree = entry(entries, AMOEBA_ID)["worktrees"][0]
        worktree["developmentPhase"] = "Phase 7: Testing"

    cf_rig.write(derived(move))
    cf_rig.tick()

    assert cf_rig.snapshots()[-1].changed == [
        {
            "worktree_id": DEFAULT_WORKTREE_ID,
            "field": "developmentPhase",
            "from": "Phase 6: Implementation",
            "to": "Phase 7: Testing",
        }
    ]


def test_one_error_when_the_file_goes_bad_and_one_info_when_it_recovers(
    cf_rig: CFRig, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="amoeba.process.cf_watch")
    cf_rig.write()
    _watching(cf_rig, AMOEBA_ID, OTHER_ID)
    cf_rig.tick()
    cf_rig.write(b"{}")
    for _ in range(3):
        cf_rig.tick()  # returns normally every interval
    cf_rig.write()
    cf_rig.tick()

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    recoveries = [r for r in caplog.records if "usable again" in r.getMessage()]
    assert len(errors) == 1
    assert len(recoveries) == 1


def test_a_link_level_failure_does_not_log_a_file_problem(
    cf_rig: CFRig, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="amoeba.process.cf_watch")
    cf_rig.write()
    _watching(cf_rig, "project_nope")

    cf_rig.tick()

    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


def test_the_resolved_path_is_logged_once_on_the_first_tick(
    cf_rig: CFRig, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="amoeba.process.cf_watch")
    for _ in range(3):
        cf_rig.tick()

    announcements = [
        r for r in caplog.records if str(cf_rig.data_file) in r.getMessage()
    ]
    assert len(announcements) == 1


def test_a_store_that_cannot_record_is_logged_reraised_and_retried(
    cf_rig: CFRig,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cf_rig.write()
    _watching(cf_rig, AMOEBA_ID)
    store = cf_rig.host.open_project("demo")
    original = store.record_cf_snapshot
    failures = [True]

    def flaky(snapshot: Any) -> Any:
        if failures:
            failures.pop()
            raise RuntimeError("disk on fire")
        return original(snapshot)

    monkeypatch.setattr(store, "record_cf_snapshot", flaky)

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="disk"):
        cf_rig.tick()
    assert any(
        "cannot record Context Forge snapshot" in r.getMessage() for r in caplog.records
    )
    assert cf_rig.snapshots() == []

    # The remembered key was not updated, so the next tick tries again.
    assert cf_rig.tick() is True
    assert len(cf_rig.snapshots()) == 1


def test_a_tick_starts_no_subprocess(
    cf_rig: CFRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("tick started a subprocess")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    cf_rig.write()
    _watching(cf_rig, AMOEBA_ID)

    cf_rig.tick()
    cf_rig.write(fixture_bytes())
    cf_rig.tick()
