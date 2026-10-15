"""The detection path, part (b): refusals, the label, hand recovery, store failure."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from detection_harness import (
    LABEL,
    PROJECT,
    ROUND_TWO_PART_ONE,
    STAMPED,
    SUBMITTED_AT,
    DetectionRig,
)

from amoeba.process.host import ResidentProcess
from amoeba.process.review_detection import ReviewDetectionTenant
from amoeba.process.settings import ProcessSettings
from amoeba.process.version_label import VERSION_UNAVAILABLE
from amoeba.store import (
    DetectedReview,
    DetectionOutcome,
    Store,
    StoreIntegrityError,
    SubmissionKind,
)
from amoeba.store.verdict_payload import verdict_to_payload
from amoeba.upstream.squadron import (
    parse_review_artifact,
    review_record_id,
    to_verdict_input,
)

SETTLE_SCANS = 2
STAMPED_SLICE = "squadron-review-parser-and-ingest"
STAMPED_VERSION = "0.21.9"


@pytest.fixture
def watched(rig: DetectionRig) -> DetectionRig:
    """An empty, baselined watch. No slice node unless a test seeds one."""
    rig.watch()
    rig.run_scans()
    return rig


def _only_detection(rig: DetectionRig) -> DetectedReview:
    [detection] = rig.store.detections(PROJECT)
    return detection


# --------------------------------------------------------------------------
# Refusals
# --------------------------------------------------------------------------


def test_no_slice_node_is_unattributed_with_no_candidates(
    watched: DetectionRig,
) -> None:
    watched.copy(ROUND_TWO_PART_ONE)
    watched.run_scans(SETTLE_SCANS)

    detection = _only_detection(watched)
    assert detection.outcome is DetectionOutcome.UNATTRIBUTED
    assert detection.detail is not None and "candidates: []" in detection.detail
    assert detection.record_id is not None
    assert detection.node_id is None
    assert watched.store.nodes_for_project(PROJECT) == []
    assert watched.store.verdicts(PROJECT) == []


def test_two_matching_nodes_are_both_named(watched: DetectionRig) -> None:
    first = watched.seed_slice_node()
    second = watched.seed_slice_node()
    watched.copy(ROUND_TWO_PART_ONE)
    watched.run_scans(SETTLE_SCANS)

    detection = _only_detection(watched)
    assert detection.outcome is DetectionOutcome.UNATTRIBUTED
    assert detection.detail is not None
    assert first in detection.detail and second in detection.detail
    assert watched.store.verdicts(PROJECT) == []


def test_a_non_review_is_unparseable_until_its_bytes_change(
    watched: DetectionRig,
) -> None:
    notes = watched.reviews_dir / "notes.md"
    notes.write_text("# not a review\n")
    watched.run_scans(SETTLE_SCANS + 3)
    assert [d.outcome for d in watched.store.detections(PROJECT)] == [
        DetectionOutcome.UNPARSEABLE
    ]

    notes.write_text("# still not a review, but different\n")
    watched.run_scans(SETTLE_SCANS)
    assert [d.outcome for d in watched.store.detections(PROJECT)] == [
        DetectionOutcome.UNPARSEABLE
    ] * 2


# --------------------------------------------------------------------------
# The version label
# --------------------------------------------------------------------------


def _recorded_version(rig: DetectionRig) -> str:
    [verdict] = rig.store.verdicts(PROJECT)
    return verdict.provenance.upstream_version


def test_an_unstamped_file_records_the_tenant_label(watched: DetectionRig) -> None:
    watched.seed_slice_node()
    watched.copy(ROUND_TWO_PART_ONE)
    watched.run_scans(SETTLE_SCANS)
    assert _recorded_version(watched) == LABEL


def test_a_stamped_file_keeps_its_own_stamp(watched: DetectionRig) -> None:
    watched.seed_slice_node(STAMPED_SLICE)
    watched.copy(STAMPED)
    watched.run_scans(SETTLE_SCANS)
    assert _recorded_version(watched) == STAMPED_VERSION


def test_an_unavailable_label_is_recorded_as_the_marker(watched: DetectionRig) -> None:
    watched.tenant = watched.new_tenant(label=VERSION_UNAVAILABLE)
    watched.seed_slice_node()
    watched.copy(ROUND_TWO_PART_ONE)
    watched.run_scans(SETTLE_SCANS)
    assert _recorded_version(watched) == VERSION_UNAVAILABLE


# --------------------------------------------------------------------------
# Hand recovery of an unattributed review
# --------------------------------------------------------------------------


def _ingest_by_hand(store: Store, path: Path, node_id: str) -> None:
    """What ``amoeba ingest review`` does: parse, compose, apply a verdict."""
    parsed = parse_review_artifact(path.read_text(encoding="utf-8"))
    verdict = to_verdict_input(
        parsed, node_id=node_id, upstream_version=LABEL, source_path=str(path)
    )
    store.apply_submission(
        submission_id=review_record_id(parsed),
        project_id=PROJECT,
        kind=SubmissionKind.VERDICT,
        submitted_by="pm",
        submitted_at=SUBMITTED_AT,
        payload=verdict_to_payload(verdict),
    )


def test_an_unattributed_review_ingested_by_hand_shows_recorded_since(
    watched: DetectionRig,
) -> None:
    path = watched.copy(ROUND_TWO_PART_ONE)
    watched.run_scans(SETTLE_SCANS)
    detection = _only_detection(watched)
    assert detection.record_id is not None
    assert watched.store.recorded_since(PROJECT, detection.record_id) is False

    node_id = watched.seed_slice_node()
    _ingest_by_hand(watched.store, path, node_id)
    assert watched.store.recorded_since(PROJECT, detection.record_id) is True

    _ingest_by_hand(watched.store, path, node_id)
    assert len(watched.store.verdicts(PROJECT)) == 1


# --------------------------------------------------------------------------
# A store that cannot record stops the process
# --------------------------------------------------------------------------


def _refuse(*_args: object, **_kwargs: object) -> object:
    raise StoreIntegrityError("the store refused the write")


def test_a_store_failure_is_logged_and_raised_writing_nothing(
    watched: DetectionRig,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    watched.seed_slice_node()
    path = watched.copy(ROUND_TWO_PART_ONE)
    watched.run_scans()
    monkeypatch.setattr(Store, "record_detected_verdict", _refuse)

    with caplog.at_level(logging.ERROR), pytest.raises(StoreIntegrityError):
        watched.run_scans()

    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any(str(path) in message for message in errors)
    assert watched.store.detections(PROJECT) == []
    assert watched.store.verdicts(PROJECT) == []


def test_a_store_failure_ends_the_resident_process(
    watched: DetectionRig,
    supervisor_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watched.seed_slice_node()
    watched.copy(ROUND_TWO_PART_ONE)
    watched.host.stores.close_all()
    monkeypatch.setattr(Store, "record_detected_verdict", _refuse)
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    process = ResidentProcess(
        ProcessSettings(
            idle_interval_seconds=0.01,
            review_scan_interval_seconds=0.01,
            sq_runs_dir=runs_dir,
        ),
        store_dir=supervisor_dir,
        version="test",
        tenants=(ReviewDetectionTenant(version_label=LABEL),),
    )

    with pytest.raises(StoreIntegrityError):
        process.run()
