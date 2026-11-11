"""``mark_read`` (slice 224, 2.6): outcomes, rejections and concurrent calls."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from store.decision_support import (
    CORE,
    FIRST,
    LINT,
    SECOND,
    automatic_answer,
    seed_programs,
    waiting_then_pm,
)

from amoeba.operations.decisions import decisions
from amoeba.operations.mark_read import MarkReadOutcome, mark_read
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.decisions import read_marker
from amoeba.store.store import Store
from operations.pause_support import build_deps


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


@pytest.fixture
def seqs(store: Store) -> list[int]:
    return [
        automatic_answer(store, FIRST, CORE, 1),
        waiting_then_pm(store, SECOND, LINT, 2),
    ]


def _marker(store: Store) -> int:
    with store.read() as transaction:
        return read_marker(transaction)


def test_a_seq_the_caller_saw_moves_the_marker(store: Store, seqs: list[int]) -> None:
    result = mark_read(store, {"through": seqs[0]})

    assert result.outcome is MarkReadOutcome.MOVED
    assert (result.previous, result.current) == (0, seqs[0])
    assert _marker(store) == seqs[0]


@pytest.mark.parametrize("lower", [0, 1])
def test_an_equal_or_lower_through_is_unchanged_and_never_moves_back(
    store: Store, seqs: list[int], lower: int
) -> None:
    mark_read(store, {"through": seqs[1]})

    result = mark_read(store, {"through": min(lower, seqs[1])})

    assert result.outcome is MarkReadOutcome.UNCHANGED
    assert (result.previous, result.current) == (seqs[1], seqs[1])
    assert _marker(store) == seqs[1]


def test_beyond_the_last_record_is_rejected_and_leaves_the_marker(
    store: Store, seqs: list[int]
) -> None:
    result = mark_read(store, {"through": seqs[1] + 1})

    assert result.outcome is MarkReadOutcome.REJECTED
    assert result.rejection is RejectCode.BEYOND_LAST_RECORD
    assert (result.previous, result.current) == (0, 0)
    assert _marker(store) == 0


def test_zero_on_an_empty_store_is_unchanged(store: Store) -> None:
    result = mark_read(store, {"through": 0})

    assert result.outcome is MarkReadOutcome.UNCHANGED
    assert (result.previous, result.current) == (0, 0)


def test_one_on_an_empty_store_is_beyond_the_last_record(store: Store) -> None:
    result = mark_read(store, {"through": 1})

    assert result.rejection is RejectCode.BEYOND_LAST_RECORD


@pytest.mark.parametrize(
    "document",
    [
        {"through": -1},
        {"through": "3"},
        {"through": 1.5},
        {"through": True},
        {},
        {"through": 1, "x": 2},
    ],
)
def test_a_negative_or_non_integer_through_is_malformed(
    store: Store, seqs: list[int], document: object
) -> None:
    result = mark_read(store, document)

    assert result.outcome is MarkReadOutcome.REJECTED
    assert result.rejection is RejectCode.MALFORMED
    assert result.problems
    assert result.previous is None
    assert _marker(store) == 0


def test_two_threads_advancing_to_different_values_leave_the_higher(
    store: Store, seqs: list[int], tmp_path: Path
) -> None:
    results: list[MarkReadOutcome] = []
    barrier = threading.Barrier(2)

    def advance(through: int) -> None:
        with Store.open(store.path) as own:
            barrier.wait()
            results.append(mark_read(own, {"through": through}).outcome)

    threads = [
        threading.Thread(target=advance, args=(through,))
        for through in (seqs[0], seqs[1])
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert _marker(store) == seqs[1]
    assert MarkReadOutcome.REJECTED not in results


def test_a_record_written_after_a_decisions_call_stays_unread(
    store: Store, seqs: list[int], tmp_path: Path
) -> None:
    rig = build_deps(tmp_path, polls={}, spawns=[])
    deps = replace(rig.deps, project_names=lambda: {CORE: "core", LINT: "lint"})
    listed = decisions(store, {}, deps=deps)
    assert listed.read_through == seqs[1]
    late = waiting_then_pm(store, replace(FIRST, run_id="late-run"), CORE, 9)

    mark_read(store, {"through": listed.read_through})
    after = decisions(store, {}, deps=deps)

    assert [record.seq for record in after.records] == [late]
