"""Baselining: files present at registration are never ingested (LLD)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest
from detection_harness import (
    PROJECT,
    ROUND_ONE_PART_ONE,
    ROUND_TWO_PART_ONE,
    DetectionRig,
)

import amoeba.process.review_detection as review_detection
from amoeba.store import ChangeKind, DetectionOutcome, ReviewWatch


def _watch(rig: DetectionRig) -> ReviewWatch:
    [watch] = rig.store.watches(PROJECT)
    return watch


def _records(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == level and r.name == review_detection.__name__
    ]


def test_existing_files_become_silent_baseline_rows(rig: DetectionRig) -> None:
    rig.seed_slice_node()
    rig.copy(ROUND_ONE_PART_ONE)
    rig.copy(ROUND_TWO_PART_ONE)
    rig.watch()

    rig.run_scans()

    rows = rig.store.detections(PROJECT)
    assert [r.outcome for r in rows] == [DetectionOutcome.BASELINE] * 2
    assert sorted(Path(r.path).name for r in rows) == sorted(
        [ROUND_ONE_PART_ONE, ROUND_TWO_PART_ONE]
    )
    assert _watch(rig).baselined_at is not None
    assert rig.store.verdicts(PROJECT) == []
    kinds = {c.kind for c in rig.store.changes(PROJECT, limit=100)}
    assert ChangeKind.REVIEW_DETECTED not in kinds


def test_a_directory_registered_before_it_exists_waits_then_baselines(
    rig: DetectionRig, caplog: pytest.LogCaptureFixture
) -> None:
    rig.reviews_dir.rmdir()
    rig.watch()
    with caplog.at_level(logging.INFO):
        rig.run_scans(3)
        assert len(_records(caplog, logging.ERROR)) == 1
        assert rig.store.detections(PROJECT) == []
        assert _watch(rig).baselined_at is None

        rig.reviews_dir.mkdir()
        rig.copy(ROUND_ONE_PART_ONE)
        rig.run_scans()

    assert any("reachable again" in m for m in _records(caplog, logging.INFO))
    assert len(rig.store.detections(PROJECT)) == 1
    assert _watch(rig).baselined_at is not None


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads mode-000 files")
def test_one_unreadable_file_holds_the_whole_baseline(
    rig: DetectionRig, caplog: pytest.LogCaptureFixture
) -> None:
    rig.copy(ROUND_ONE_PART_ONE)
    blocked = rig.copy(ROUND_TWO_PART_ONE)
    blocked.chmod(0)
    rig.watch()
    try:
        with caplog.at_level(logging.WARNING):
            rig.run_scans(3)
        assert rig.store.detections(PROJECT) == []
        assert _watch(rig).baselined_at is None
        warnings = _records(caplog, logging.WARNING)
        assert len(warnings) == 1
        assert blocked.name in warnings[0]
    finally:
        blocked.chmod(0o644)

    rig.run_scans()
    assert len(rig.store.detections(PROJECT)) == 2


def test_a_file_deleted_between_listing_and_read_is_left_out(
    rig: DetectionRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig.copy(ROUND_ONE_PART_ONE)
    gone = rig.copy(ROUND_TWO_PART_ONE)
    rig.watch()
    real_read = Path.read_bytes

    def vanishing(self: Path) -> bytes:
        if self == gone:
            raise FileNotFoundError(self)
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", vanishing)
    rig.run_scans()

    [row] = rig.store.detections(PROJECT)
    assert Path(row.path).name == ROUND_ONE_PART_ONE
    assert _watch(rig).baselined_at is not None


def test_two_ticks_inside_the_interval_scan_once(
    rig: DetectionRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig.reviews_dir.rmdir()
    rig.watch()
    listings: list[Path] = []
    real_list = review_detection.list_review_files

    def counting(directory: Path) -> list[Path]:
        listings.append(directory)
        return real_list(directory)

    monkeypatch.setattr(review_detection, "list_review_files", counting)
    rig.tenant.tick(rig.host)
    rig.tenant.tick(rig.host)
    assert len(listings) == 1


def test_an_inactive_watch_is_never_baselined(rig: DetectionRig) -> None:
    rig.copy(ROUND_ONE_PART_ONE)
    rig.watch(active=False)
    rig.run_scans(2)
    assert rig.store.detections(PROJECT) == []
    assert _watch(rig).baselined_at is None


def test_a_baselined_watch_is_not_baselined_again(rig: DetectionRig) -> None:
    rig.copy(ROUND_ONE_PART_ONE)
    rig.watch()
    rig.run_scans()
    baselined_at = _watch(rig).baselined_at
    rig.run_scans(3)
    assert len(rig.store.detections(PROJECT)) == 1
    assert _watch(rig).baselined_at == baselined_at
