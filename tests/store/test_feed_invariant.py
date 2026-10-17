"""The feed invariant: replaying the log from seq 0 reconciles with the store.

A scripted sequence drives every write path that exists. Then the feed is
replayed and compared against each tracked table. Every ``ChangeKind`` must
appear, so a kind whose trigger was never written, or whose SQL literal drifted
from the enum, fails here.
"""

from __future__ import annotations

from cf_harness import failure, observed
from evidence_harness import check_input, provider_failure, verdict_input
from feed_harness import (
    escalate_by_recovery,
    post_intent,
    raw_changes,
    resolve_by_submission,
)

from amoeba.store import (
    BlockedKind,
    CFSnapshotOutcome,
    Channel,
    NodeKind,
    NodeStatus,
    Store,
)
from amoeba.store.feed_models import (
    SILENT_OUTCOMES,
    Change,
    ChangeKind,
    DetectionInput,
    DetectionOutcome,
)

PROJECT = "demo"


def _run_sequence(store: Store) -> None:
    """Drive every write path once or more."""
    root = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="r").id
    gate = store.create_node(
        project_id=PROJECT, kind=NodeKind.GATE, title="g", parent_id=root
    ).id
    store.update_node_status(gate, NodeStatus.IN_PROGRESS)
    store.update_node_status(gate, NodeStatus.IN_PROGRESS)
    store.block(root, kind=BlockedKind.HUMAN, context="decide")
    resolve_by_submission(store, "s-resolve", root, PROJECT)
    store.record_verdict(verdict_input("v-1", root), project_id=PROJECT)
    store.record_verdict(verdict_input("v-1", root), project_id=PROJECT)
    store.record_verdict(provider_failure("v-2", root), project_id=PROJECT)
    store.record_check(check_input("c-1", root), project_id=PROJECT)
    store.record_check(check_input("c-1", root), project_id=PROJECT)
    post_intent(store, "s-intent", gate, PROJECT)
    store.update_node_status(gate, NodeStatus.DONE)
    escalate_by_recovery(store, root, PROJECT)
    for index, outcome in enumerate(DetectionOutcome):
        store.record_detection(
            DetectionInput(
                project_id=PROJECT,
                path=f"/r/{index}.md",
                digest="d",
                outcome=outcome,
                node_id=root,
            )
        )
    _record_cf_snapshots(store)


def _record_cf_snapshots(store: Store) -> None:
    """One snapshot per outcome, then a re-check that records nothing (108, D6).

    The re-check is the tenant's job: it compares against the latest rows and
    writes only when something changed. Here it is the reads alone, which must
    leave the feed as it was.
    """
    for outcome in CFSnapshotOutcome:
        store.record_cf_snapshot(
            observed(PROJECT, "cf-1")
            if outcome is CFSnapshotOutcome.OBSERVED
            else failure(PROJECT, "cf-1", outcome)
        )
    store.latest_cf_snapshots(PROJECT, "cf-1")
    store.cf_snapshots(PROJECT)


def _rebuilt_statuses(changes: list[Change]) -> dict[str, object]:
    statuses: dict[str, object] = {}
    for change in changes:
        if change.kind is ChangeKind.NODE_CREATED:
            statuses[change.subject_id] = change.payload["status"]
        elif change.kind is ChangeKind.NODE_STATUS_CHANGED:
            statuses[change.subject_id] = change.payload["to"]
    return statuses


def _subjects(changes: list[Change], kind: ChangeKind) -> list[str]:
    return [change.subject_id for change in changes if change.kind is kind]


def reconcile(store: Store, project_id: str) -> list[str]:
    """Differences between the replayed feed and the store; empty means consistent."""
    changes = raw_changes(store, project_id)
    differences: list[str] = []

    nodes = {node.id: node.status.value for node in store.nodes_for_project(project_id)}
    created = _subjects(changes, ChangeKind.NODE_CREATED)
    if sorted(created) != sorted(nodes):
        differences.append(f"node ids: feed {sorted(created)} != store {sorted(nodes)}")
    if _rebuilt_statuses(changes) != nodes:
        differences.append(f"statuses: feed {_rebuilt_statuses(changes)} != {nodes}")

    verdict_ids = [verdict.id for verdict in store.verdicts(project_id)]
    if _subjects(changes, ChangeKind.VERDICT_RECORDED) != verdict_ids:
        differences.append(f"verdict ids differ from {verdict_ids}")

    check_ids = [check.id for check in store.checks(project_id)]
    if _subjects(changes, ChangeKind.CHECK_RECORDED) != check_ids:
        differences.append(f"check ids differ from {check_ids}")

    message_ids = sorted(
        message.id
        for channel in Channel
        for message in store.messages(project_id, channel=channel)
    )
    if sorted(_subjects(changes, ChangeKind.MESSAGE_POSTED)) != message_ids:
        differences.append(f"message ids differ from {message_ids}")

    loud_ids = sorted(
        str(detection.id)
        for detection in store.detections(project_id)
        if detection.outcome not in SILENT_OUTCOMES
    )
    if sorted(_subjects(changes, ChangeKind.REVIEW_DETECTED)) != loud_ids:
        differences.append(f"ledger ids differ from {loud_ids}")

    snapshot_ids = [str(snapshot.id) for snapshot in store.cf_snapshots(project_id)]
    if _subjects(changes, ChangeKind.CF_PROJECT_CHANGED) != snapshot_ids:
        differences.append(f"cf snapshot ids differ from {snapshot_ids}")

    return differences


def test_the_sequence_reconciles_with_every_tracked_table(store: Store) -> None:
    _run_sequence(store)
    assert reconcile(store, PROJECT) == []


def test_every_change_kind_appears(store: Store) -> None:
    _run_sequence(store)
    seen = {change.kind for change in raw_changes(store, PROJECT)}
    assert set(ChangeKind) <= seen


def test_seq_has_no_gaps(store: Store) -> None:
    _run_sequence(store)
    seqs = [change.seq for change in raw_changes(store, PROJECT)]
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))
