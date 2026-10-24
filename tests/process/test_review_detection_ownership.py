"""D5: detection defers while the Runner owns a review, and skips its files."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import pytest
from detection_harness import PROJECT, ROUND_TWO_PART_ONE, DetectionRig
from sq_run_fixtures import sq_run_parameters

import amoeba.process.review_detection as review_detection
from amoeba.process.review_scan import content_digest
from amoeba.store import (
    ChangeKind,
    CommandKind,
    DetectionInput,
    DetectionOutcome,
    JournalOutcome,
)
from amoeba.store.review_sources import DetectedFile, DirectoryReviewSource

SETTLE_SCANS = 2
SQ_PARAMETERS: dict[str, object] = sq_run_parameters({"pipeline": "p6", "params": {}})
CF_PARAMETERS: dict[str, object] = {
    "project": "p",
    "expected": {},
    "checkout": "/work/p",
}


class CountingSource:
    """A real directory source that counts its polls."""

    polls = 0

    def __init__(self, directory: Path) -> None:
        self._inner = DirectoryReviewSource(directory)

    def poll(self) -> Sequence[DetectedFile]:
        CountingSource.polls += 1
        return self._inner.poll()


@pytest.fixture
def owned(rig: DetectionRig) -> DetectionRig:
    """A slice node, a counting source, and a baselined empty watch."""
    CountingSource.polls = 0
    rig.tenant = rig.new_tenant(source_factory=CountingSource)
    rig.seed_slice_node()
    rig.watch()
    rig.run_scans()
    return rig


def _issue(rig: DetectionRig, kind: CommandKind = CommandKind.SQ_RUN) -> str:
    [node] = rig.store.nodes_for_project(PROJECT)
    parameters = SQ_PARAMETERS if kind is CommandKind.SQ_RUN else CF_PARAMETERS
    return rig.store.journal_issue(node.id, kind=kind, parameters=parameters).id


def _logged(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == level and r.name == review_detection.__name__
    ]


def test_an_open_review_entry_defers_until_it_resolves(
    owned: DetectionRig, caplog: pytest.LogCaptureFixture
) -> None:
    entry_id = _issue(owned)
    owned.copy(ROUND_TWO_PART_ONE)
    polls_before = CountingSource.polls

    with caplog.at_level(logging.INFO):
        owned.run_scans(4)
        assert owned.store.detections(PROJECT) == []
        assert CountingSource.polls == polls_before
        assert len(_logged(caplog, logging.WARNING)) == 1

        owned.store.journal_resolve(entry_id, outcome=JournalOutcome.COMPLETED)
        owned.run_scans(SETTLE_SCANS)

    assert any("resuming" in m for m in _logged(caplog, logging.INFO))
    assert [d.outcome for d in owned.store.detections(PROJECT)] == [
        DetectionOutcome.INGESTED
    ]


def test_a_new_watch_is_baselined_while_deferring(rig: DetectionRig) -> None:
    rig.seed_slice_node()
    _issue(rig)
    rig.copy(ROUND_TWO_PART_ONE)
    rig.watch()
    rig.run_scans()
    assert [d.outcome for d in rig.store.detections(PROJECT)] == [
        DetectionOutcome.BASELINE
    ]


def test_a_runner_issued_file_is_never_ingested(owned: DetectionRig) -> None:
    path = owned.copy(ROUND_TWO_PART_ONE)
    owned.store.record_detection(
        DetectionInput(
            project_id=PROJECT,
            path=str(path),
            digest=content_digest(path.read_bytes()),
            outcome=DetectionOutcome.RUNNER_ISSUED,
        )
    )
    owned.run_scans(SETTLE_SCANS + 2)

    assert [d.outcome for d in owned.store.detections(PROJECT)] == [
        DetectionOutcome.RUNNER_ISSUED
    ]
    assert owned.store.verdicts(PROJECT) == []
    kinds = {c.kind for c in owned.store.changes(PROJECT, limit=100)}
    assert ChangeKind.REVIEW_DETECTED not in kinds


def test_an_open_entry_of_another_kind_does_not_defer(owned: DetectionRig) -> None:
    _issue(owned, CommandKind.CF_WRITE)
    owned.copy(ROUND_TWO_PART_ONE)
    owned.run_scans(SETTLE_SCANS)
    assert [d.outcome for d in owned.store.detections(PROJECT)] == [
        DetectionOutcome.INGESTED
    ]
