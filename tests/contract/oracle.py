"""The proof's two oracles (slice 110, D5, D6).

*End state.* A project's store is read through the public read API into a
``ProjectState`` — facts grouped by category — and compared with the state the
scenario declares. A missing fact, an extra fact, or a different count fails.

*Feed replay.* A subscriber's changes, replayed from ``seq`` 0, must rebuild
every node's final status, and their ``seq`` must rise strictly with no gap. That
is what 106 promised subscribers: the feed alone is enough to reconstruct state.

Facts are strings built by :func:`fact` from enum members, so no vocabulary value
is spelled as a literal here or in the declaration.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path

from amoeba.store import (
    BlockedKind,
    Change,
    ChangeKind,
    Channel,
    CommandKind,
    DetectionOutcome,
    JournalOutcome,
    JournalResolver,
    NodeKind,
    NodeStatus,
    Store,
    SubmissionKind,
    SubmissionOutcome,
    VerdictStanding,
    project_store_path,
)


class Category(StrEnum):
    """What a fact describes."""

    NODES = "nodes"
    BLOCKED = "blocked"
    JOURNAL = "journal"
    VERDICTS = "verdicts"
    DETECTIONS = "detections"
    MESSAGES = "messages"
    SUBMISSIONS = "submissions"


type ProjectState = Mapping[Category, Counter[str]]


def fact(*parts: object) -> str:
    """One fact: its parts, joined. Enum members contribute their values."""
    return "/".join(str(part) for part in parts)


def node_fact(kind: NodeKind, status: NodeStatus) -> str:
    return fact(kind, status)


def blocked_fact(node_kind: NodeKind, blocked_kind: BlockedKind, resolved: bool) -> str:
    return fact(node_kind, blocked_kind, "resolved" if resolved else "open")


def journal_fact(
    kind: CommandKind, outcome: JournalOutcome | None, resolver: JournalResolver | None
) -> str:
    return fact(kind, outcome, resolver)


def verdict_fact(standing: VerdictStanding, from_judge_invocation: bool) -> str:
    return fact(standing, "judge-sample" if from_judge_invocation else "single")


def detection_fact(outcome: DetectionOutcome, in_reviews_dir: bool) -> str:
    return fact(outcome, "in-reviews-dir" if in_reviews_dir else "elsewhere")


def message_fact(channel: Channel, acknowledged: bool) -> str:
    return fact(channel, "acknowledged" if acknowledged else "pending")


def submission_fact(kind: SubmissionKind, outcome: SubmissionOutcome) -> str:
    return fact(kind, outcome)


def counted(*facts: str) -> Counter[str]:
    """A multiset of facts; repeat a fact to declare it more than once."""
    return Counter(facts)


def read_state(store: Store, project_id: str, reviews_dir: Path) -> ProjectState:
    """Everything the oracle compares, read through public reads only."""
    state: dict[Category, Counter[str]] = {
        category: Counter[str]() for category in Category
    }
    for node in store.nodes_for_project(project_id):
        state[Category.NODES][node_fact(node.kind, node.status)] += 1
        for blocked in store.all_blocked_states(node.id):
            state[Category.BLOCKED][
                blocked_fact(node.kind, blocked.kind, blocked.is_resolved)
            ] += 1
    for entry in store.journal_entries(project_id):
        state[Category.JOURNAL][
            journal_fact(entry.kind, entry.outcome, entry.resolved_by)
        ] += 1
    for verdict in store.verdicts(project_id):
        sampled = verdict.judge_invocation_id is not None
        state[Category.VERDICTS][verdict_fact(verdict.standing, sampled)] += 1
    for detection in store.detections(project_id):
        in_reviews_dir = Path(detection.path).parent == reviews_dir
        state[Category.DETECTIONS][
            detection_fact(detection.outcome, in_reviews_dir)
        ] += 1
    for channel in Channel:
        for message in store.messages(project_id, channel=channel):
            state[Category.MESSAGES][
                message_fact(channel, message.is_acknowledged)
            ] += 1
    for submission in store.submissions(project_id):
        state[Category.SUBMISSIONS][
            submission_fact(submission.kind, submission.outcome)
        ] += 1
    return state


def diff_state(
    project_id: str, declared: ProjectState, actual: ProjectState
) -> list[str]:
    """A readable account of every difference; empty only on an exact match."""
    lines: list[str] = []
    for category in Category:
        want = declared.get(category, Counter[str]())
        have = actual.get(category, Counter[str]())
        for name in sorted((want - have).elements()):
            lines.append(f"{project_id} {category}: missing {name}")
        for name in sorted((have - want).elements()):
            lines.append(f"{project_id} {category}: unexpected {name}")
    return lines


def locality_problems(
    supervisor_dir: Path,
    project_ids: Sequence[str],
    reviews_dirs: Mapping[str, Path],
    changes: Mapping[str, Sequence[Change]],
    ledger_paths: Mapping[str, Sequence[str]],
) -> list[str]:
    """D6: one store per project and nothing crossing between them."""
    problems: list[str] = []
    suffix = project_store_path(supervisor_dir, project_ids[0]).suffix
    expected = sorted(project_store_path(supervisor_dir, p).name for p in project_ids)
    actual = sorted(path.name for path in supervisor_dir.glob(f"*{suffix}"))
    if actual != expected:
        problems.append(f"supervisor directory holds {actual}, expected {expected}")
    for project_id in project_ids:
        foreign = [c.seq for c in changes[project_id] if c.project_id != project_id]
        if foreign:
            problems.append(f"{project_id} feed carries foreign changes {foreign}")
        for other in project_ids:
            if other == project_id:
                continue
            for path in ledger_paths[project_id]:
                if Path(path).parent == reviews_dirs[other]:
                    problems.append(f"{project_id} ledger holds {other}'s file {path}")
    return problems


def sequence_problems(changes: Sequence[Change]) -> list[str]:
    """``seq`` must rise by exactly one from the first change: no gap, no repeat."""
    problems: list[str] = []
    if changes and changes[0].seq != 1:
        problems.append(f"the feed starts at seq {changes[0].seq}, not 1")
    for previous, current in zip(changes, changes[1:], strict=False):
        if current.seq != previous.seq + 1:
            problems.append(f"seq {previous.seq} is followed by {current.seq}")
    return problems


def replay_statuses(changes: Sequence[Change]) -> dict[str, NodeStatus]:
    """Rebuild node statuses from the feed alone: created sets, changed moves."""
    statuses: dict[str, NodeStatus] = {}
    for change in changes:
        if change.node_id is None:
            continue
        if change.kind is ChangeKind.NODE_CREATED:
            statuses[change.node_id] = NodeStatus(str(change.payload["status"]))
        elif change.kind is ChangeKind.NODE_STATUS_CHANGED:
            statuses[change.node_id] = NodeStatus(str(change.payload["to"]))
    return statuses


def replay_problems(
    changes: Sequence[Change], actual: Mapping[str, NodeStatus]
) -> list[str]:
    """Differences between the replayed statuses and the store's, per node."""
    replayed = replay_statuses(changes)
    problems = [
        f"node {node_id}: feed says {replayed.get(node_id)}, store says {status}"
        for node_id, status in actual.items()
        if replayed.get(node_id) != status
    ]
    problems += [
        f"node {node_id}: on the feed but not in the store"
        for node_id in replayed
        if node_id not in actual
    ]
    return problems + sequence_problems(changes)
