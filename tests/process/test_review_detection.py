"""The detection path, part (a): ingest, provider failure, hand edit, restart, race."""

from __future__ import annotations

from pathlib import Path

import pytest
from detection_harness import (
    PROJECT,
    PROVIDER_FAILURE,
    ROUND_ONE_PART_ONE,
    ROUND_TWO_PART_ONE,
    DetectionRig,
)

from amoeba.store import (
    ChangeKind,
    DetectionOutcome,
    RecordSource,
    VerdictStanding,
)

#: A file settles across two scans: seen, then unchanged.
SETTLE_SCANS = 2


@pytest.fixture
def ready(rig: DetectionRig) -> DetectionRig:
    """A slice node and an empty, baselined watch."""
    rig.seed_slice_node()
    rig.watch()
    rig.run_scans()
    return rig


def _kinds_since(rig: DetectionRig, after: int) -> list[ChangeKind]:
    return [c.kind for c in rig.store.changes(PROJECT, after=after, limit=100)]


def _head(rig: DetectionRig) -> int:
    changes = rig.store.changes(PROJECT, limit=1000)
    return changes[-1].seq if changes else 0


def test_two_rounds_become_two_verdicts_on_the_slice_node(ready: DetectionRig) -> None:
    rig = ready
    [node] = rig.store.nodes_for_project(PROJECT)
    for name in (ROUND_ONE_PART_ONE, ROUND_TWO_PART_ONE):
        head = _head(rig)
        path = rig.copy(name)
        rig.run_scans(SETTLE_SCANS)

        verdict = rig.store.verdicts(PROJECT)[-1]
        assert verdict.node_id == node.id
        assert verdict.provenance.source is RecordSource.ARTIFACT_FRONTMATTER
        assert verdict.provenance.source_path == str(path)
        ledger = rig.store.detections(PROJECT)[-1]
        assert (ledger.outcome, ledger.verdict_id) == (
            DetectionOutcome.INGESTED,
            verdict.id,
        )
        assert _kinds_since(rig, head) == [
            ChangeKind.VERDICT_RECORDED,
            ChangeKind.REVIEW_DETECTED,
        ]
    assert len(rig.store.verdicts(PROJECT)) == 2


def test_the_captured_provider_failure_keeps_its_standing(ready: DetectionRig) -> None:
    ready.copy(PROVIDER_FAILURE)
    ready.run_scans(SETTLE_SCANS)
    [verdict] = ready.store.verdicts(PROJECT)
    assert verdict.standing is VerdictStanding.PROVIDER_FAILURE


def test_a_hand_edit_points_a_new_row_at_the_same_verdict(ready: DetectionRig) -> None:
    rig = ready
    path = rig.copy(ROUND_TWO_PART_ONE)
    rig.run_scans(SETTLE_SCANS)
    [verdict] = rig.store.verdicts(PROJECT)
    head = _head(rig)

    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("---\n", "---\nresolution: accepted\n", 1))
    rig.run_scans(SETTLE_SCANS)

    assert [v.id for v in rig.store.verdicts(PROJECT)] == [verdict.id]
    ingested = rig.store.detections(PROJECT, outcome=DetectionOutcome.INGESTED)
    assert [d.verdict_id for d in ingested] == [verdict.id, verdict.id]
    assert len({d.digest for d in ingested}) == 2
    assert _kinds_since(rig, head) == [ChangeKind.REVIEW_DETECTED]


def test_a_restarted_tenant_re_ingests_nothing(ready: DetectionRig) -> None:
    rig = ready
    rig.copy(ROUND_ONE_PART_ONE)
    rig.run_scans(SETTLE_SCANS)
    before = (rig.store.verdicts(PROJECT), rig.store.detections(PROJECT))

    rig.tenant = rig.new_tenant()
    rig.run_scans(SETTLE_SCANS + 1)

    assert (rig.store.verdicts(PROJECT), rig.store.detections(PROJECT)) == before


def test_a_file_gone_at_read_writes_nothing_then_lands_when_restored(
    ready: DetectionRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = ready
    path = rig.copy(ROUND_ONE_PART_ONE)
    rig.run_scans()  # first sighting
    real_read = Path.read_bytes

    def vanishing(self: Path) -> bytes:
        if self == path:
            raise FileNotFoundError(self)
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", vanishing)
    rig.run_scans()
    assert rig.store.detections(PROJECT) == []

    monkeypatch.setattr(Path, "read_bytes", real_read)
    rig.run_scans(SETTLE_SCANS)
    assert [d.outcome for d in rig.store.detections(PROJECT)] == [
        DetectionOutcome.INGESTED
    ]
