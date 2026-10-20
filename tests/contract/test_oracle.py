"""Each oracle fails when it should, and passes only on an exact match."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from amoeba.store import (
    Change,
    ChangeKind,
    NodeKind,
    NodeStatus,
    Store,
)
from contract.oracle import (
    Category,
    ProjectState,
    counted,
    diff_state,
    locality_problems,
    node_fact,
    read_state,
    replay_problems,
    replay_statuses,
    sequence_problems,
)
from contract.scenario import ALPHA, BETA, STEPS

PROJECT = "demo"
MOMENT = datetime(2026, 10, 20, tzinfo=UTC)


def _change(
    seq: int,
    kind: ChangeKind,
    node_id: str | None,
    payload: dict[str, object],
    project_id: str = PROJECT,
) -> Change:
    return Change(
        seq=seq,
        project_id=project_id,
        kind=kind,
        node_id=node_id,
        subject_id=node_id or "",
        payload=payload,
        recorded_at=MOMENT,
    )


def _created(seq: int, node_id: str, status: NodeStatus) -> Change:
    return _change(seq, ChangeKind.NODE_CREATED, node_id, {"status": status.value})


def _moved(seq: int, node_id: str, status: NodeStatus) -> Change:
    return _change(seq, ChangeKind.NODE_STATUS_CHANGED, node_id, {"to": status.value})


def _empty_state() -> dict[Category, Counter[str]]:
    return {category: Counter[str]() for category in Category}


# --------------------------------------------------------------------------
# The end-state oracle
# --------------------------------------------------------------------------


def test_an_exact_match_has_an_empty_diff(store: Store) -> None:
    store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s")
    declared: ProjectState = {
        **_empty_state(),
        Category.NODES: counted(node_fact(NodeKind.SLICE, NodeStatus.RUNNABLE)),
    }

    actual = read_state(store, PROJECT, Path("/reviews"))

    assert diff_state(PROJECT, declared, actual) == []


def test_an_extra_row_is_reported(store: Store) -> None:
    store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s")
    store.create_node(project_id=PROJECT, kind=NodeKind.GATE, title="g")
    declared: ProjectState = {
        **_empty_state(),
        Category.NODES: counted(node_fact(NodeKind.SLICE, NodeStatus.RUNNABLE)),
    }

    problems = diff_state(
        PROJECT, declared, read_state(store, PROJECT, Path("/reviews"))
    )

    assert problems == [f"{PROJECT} nodes: unexpected gate/runnable"]


def test_a_missing_row_is_reported(store: Store) -> None:
    store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s")
    declared: ProjectState = {
        **_empty_state(),
        Category.NODES: counted(
            node_fact(NodeKind.SLICE, NodeStatus.RUNNABLE),
            node_fact(NodeKind.GATE, NodeStatus.RUNNABLE),
        ),
    }

    problems = diff_state(
        PROJECT, declared, read_state(store, PROJECT, Path("/reviews"))
    )

    assert problems == [f"{PROJECT} nodes: missing gate/runnable"]


def test_a_wrong_count_is_reported(store: Store) -> None:
    for title in ("a", "b"):
        store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title=title)
    declared: ProjectState = {
        **_empty_state(),
        Category.NODES: counted(node_fact(NodeKind.SLICE, NodeStatus.RUNNABLE)),
    }

    problems = diff_state(
        PROJECT, declared, read_state(store, PROJECT, Path("/reviews"))
    )

    assert problems == [f"{PROJECT} nodes: unexpected slice/runnable"]


def test_a_different_status_is_reported_as_missing_and_unexpected(
    store: Store,
) -> None:
    node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s")
    store.update_node_status(node.id, NodeStatus.DONE)
    declared: ProjectState = {
        **_empty_state(),
        Category.NODES: counted(node_fact(NodeKind.SLICE, NodeStatus.RUNNABLE)),
    }

    problems = diff_state(
        PROJECT, declared, read_state(store, PROJECT, Path("/reviews"))
    )

    assert sorted(problems) == [
        f"{PROJECT} nodes: missing slice/runnable",
        f"{PROJECT} nodes: unexpected slice/done",
    ]


# --------------------------------------------------------------------------
# Locality (D6)
# --------------------------------------------------------------------------


def _locality(
    supervisor: Path,
    changes: dict[str, Sequence[Change]],
    ledger: dict[str, Sequence[str]],
) -> list[str]:
    reviews = {ALPHA: Path("/reviews/alpha"), BETA: Path("/reviews/beta")}
    return locality_problems(supervisor, (ALPHA, BETA), reviews, changes, ledger)


def test_two_store_files_and_no_crossing_is_clean(tmp_path: Path) -> None:
    for name in ("alpha.sqlite3", "beta.sqlite3", "alpha.sqlite3-wal", "lock"):
        (tmp_path / name).touch()

    own = _change(1, ChangeKind.NODE_CREATED, "n", {}, project_id=ALPHA)

    problems = _locality(
        tmp_path,
        {ALPHA: [own], BETA: []},
        {ALPHA: ["/reviews/alpha/a.md"], BETA: []},
    )

    assert problems == []


def test_a_stray_store_file_is_reported(tmp_path: Path) -> None:
    for name in ("alpha.sqlite3", "beta.sqlite3", "gamma.sqlite3"):
        (tmp_path / name).touch()

    problems = _locality(tmp_path, {ALPHA: [], BETA: []}, {ALPHA: [], BETA: []})

    assert len(problems) == 1 and "gamma.sqlite3" in problems[0]


def test_another_projects_reviews_file_in_a_ledger_is_reported(
    tmp_path: Path,
) -> None:
    for name in ("alpha.sqlite3", "beta.sqlite3"):
        (tmp_path / name).touch()

    problems = _locality(
        tmp_path, {ALPHA: [], BETA: []}, {ALPHA: [], BETA: ["/reviews/alpha/a.md"]}
    )

    assert len(problems) == 1 and "alpha's file" in problems[0]


def test_a_foreign_change_on_a_feed_is_reported(tmp_path: Path) -> None:
    for name in ("alpha.sqlite3", "beta.sqlite3"):
        (tmp_path / name).touch()
    foreign = _change(1, ChangeKind.NODE_CREATED, "n", {}, project_id=BETA)

    problems = _locality(tmp_path, {ALPHA: [foreign], BETA: []}, {ALPHA: [], BETA: []})

    assert len(problems) == 1 and "foreign" in problems[0]


# --------------------------------------------------------------------------
# The feed-replay oracle
# --------------------------------------------------------------------------


def test_a_correct_feed_replays_to_the_stores_statuses() -> None:
    changes = [
        _created(1, "a", NodeStatus.RUNNABLE),
        _created(2, "b", NodeStatus.RUNNABLE),
        _moved(3, "a", NodeStatus.DONE),
    ]

    assert replay_statuses(changes) == {"a": NodeStatus.DONE, "b": NodeStatus.RUNNABLE}
    assert (
        replay_problems(changes, {"a": NodeStatus.DONE, "b": NodeStatus.RUNNABLE}) == []
    )


def test_a_replayed_status_that_differs_from_the_store_is_reported() -> None:
    changes = [_created(1, "a", NodeStatus.RUNNABLE)]

    problems = replay_problems(changes, {"a": NodeStatus.DONE})

    assert len(problems) == 1 and "node a" in problems[0]


def test_a_node_the_feed_never_announced_is_reported() -> None:
    problems = replay_problems([], {"ghost": NodeStatus.RUNNABLE})

    assert len(problems) == 1 and "ghost" in problems[0]


@pytest.mark.parametrize(
    ("seqs", "fragment"),
    [
        ([1, 2, 4], "2 is followed by 4"),
        ([1, 2, 2], "2 is followed by 2"),
        ([1, 3, 2], "1 is followed by 3"),
        ([2, 3], "starts at seq 2"),
    ],
)
def test_a_gap_a_repeat_or_a_bad_order_is_reported(
    seqs: list[int], fragment: str
) -> None:
    changes = [_created(seq, f"n{seq}", NodeStatus.RUNNABLE) for seq in seqs]

    problems = sequence_problems(changes)

    assert any(fragment in problem for problem in problems)


def test_a_contiguous_feed_from_one_has_no_sequence_problem() -> None:
    changes = [_created(seq, f"n{seq}", NodeStatus.RUNNABLE) for seq in (1, 2, 3)]

    assert sequence_problems(changes) == []


# --------------------------------------------------------------------------
# The scenario's shape
# --------------------------------------------------------------------------


def test_the_scenario_has_twelve_numbered_steps() -> None:
    assert [step.number for step in STEPS] == list(range(1, 13))


def test_beta_takes_part_only_in_steps_one_two_and_nine() -> None:
    with_beta = {step.number for step in STEPS if BETA in step.projects}

    assert with_beta == {1, 2, 9}


def test_every_runner_step_names_a_proof_step_and_no_other_does() -> None:
    from contract.scenario import Actor

    for step in STEPS:
        assert (step.proof_step is not None) == (step.actor is Actor.RUNNER)
