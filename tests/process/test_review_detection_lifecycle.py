"""Scan-time reachability and reactivation of a baselined watch."""

from __future__ import annotations

import logging
import shutil

import pytest
from detection_harness import (
    PROJECT,
    ROUND_ONE_PART_ONE,
    ROUND_TWO_PART_ONE,
    DetectionRig,
)

import amoeba.process.review_detection as review_detection
from amoeba.store import DetectionOutcome


def _messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == level and r.name == review_detection.__name__
    ]


def _outcomes(rig: DetectionRig) -> list[DetectionOutcome]:
    return [d.outcome for d in rig.store.detections(PROJECT)]


@pytest.fixture
def baselined(rig: DetectionRig) -> DetectionRig:
    """A slice node and a watch baselined over one existing round."""
    rig.seed_slice_node()
    rig.copy(ROUND_ONE_PART_ONE)
    rig.watch()
    rig.run_scans()
    assert _outcomes(rig) == [DetectionOutcome.BASELINE]
    return rig


def test_a_removed_directory_logs_once_and_resumes_when_restored(
    baselined: DetectionRig, caplog: pytest.LogCaptureFixture
) -> None:
    rig = baselined
    shutil.rmtree(rig.reviews_dir)
    with caplog.at_level(logging.INFO):
        rig.run_scans(3)
        assert len(_messages(caplog, logging.ERROR)) == 1

        rig.reviews_dir.mkdir()
        rig.copy(ROUND_TWO_PART_ONE)
        rig.run_scans(2)

    assert len(_messages(caplog, logging.ERROR)) == 1
    assert any("reachable again" in m for m in _messages(caplog, logging.INFO))
    assert _outcomes(rig) == [DetectionOutcome.BASELINE, DetectionOutcome.INGESTED]


def test_reactivation_detects_files_that_arrived_while_inactive(
    baselined: DetectionRig,
) -> None:
    rig = baselined
    baseline_rows = rig.store.detections(PROJECT)
    rig.watch(active=False)
    rig.copy(ROUND_TWO_PART_ONE)
    rig.run_scans(3)
    assert rig.store.detections(PROJECT) == baseline_rows

    rig.watch(active=True)
    rig.run_scans(2)

    rows = rig.store.detections(PROJECT)
    assert rows[: len(baseline_rows)] == baseline_rows
    assert [r.outcome for r in rows[len(baseline_rows) :]] == [
        DetectionOutcome.INGESTED
    ]
