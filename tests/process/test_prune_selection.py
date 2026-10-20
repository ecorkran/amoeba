"""``select_prunable``: each of D8's four conditions, failing alone."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from amoeba.process.observers.sq_runs import SquadronRun
from amoeba.process.run_pruning import PAUSED_STATUS, PRUNE_RETENTION, select_prunable

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
OWNER = "alpha"
RUN_ID = "run-20261001-review-aaaa1111"
OLD_ENOUGH = NOW - PRUNE_RETENTION - timedelta(days=1)


def _run(
    run_id: str = RUN_ID,
    *,
    status: str = PAUSED_STATUS,
    updated_at: datetime | None = OLD_ENOUGH,
) -> SquadronRun:
    return SquadronRun(
        schema_version=5,
        run_id=run_id,
        pipeline="review",
        params={},
        started_at=OLD_ENOUGH,
        status=status,
        updated_at=updated_at,
    )


def _select(
    runs: list[SquadronRun],
    *,
    owned: dict[str, str] | None = None,
    held: set[str] | None = None,
) -> tuple[SquadronRun, ...]:
    return select_prunable(
        runs,
        owned={RUN_ID: OWNER} if owned is None else owned,
        held=set() if held is None else held,
        now=NOW,
    )


def test_a_run_meeting_all_four_conditions_is_selected() -> None:
    run = _run()

    assert _select([run]) == (run,)


def test_a_run_nobody_owns_is_never_selected() -> None:
    """Condition 1: runs the PM launched are not Amoeba's to prune."""
    assert _select([_run()], owned={}) == ()


@pytest.mark.parametrize("status", ["completed", "failed", "running"])
def test_a_run_that_is_not_paused_is_not_selected(status: str) -> None:
    """Condition 2."""
    assert _select([_run(status=status)]) == ()


def test_a_run_a_live_node_still_names_is_held() -> None:
    """Condition 3: a resumed-but-not-done node's run is not offered."""
    assert _select([_run()], held={RUN_ID}) == ()


def test_a_run_younger_than_the_retention_is_not_selected() -> None:
    """Condition 4."""
    assert (
        _select([_run(updated_at=NOW - PRUNE_RETENTION + timedelta(seconds=1))]) == ()
    )


def test_a_run_exactly_at_the_retention_is_selected() -> None:
    run = _run(updated_at=NOW - PRUNE_RETENTION)

    assert _select([run]) == (run,)


def test_a_run_with_no_updated_at_is_never_selected() -> None:
    """Unknown is not a value to guess."""
    assert _select([_run(updated_at=None)]) == ()


def test_only_the_runs_meeting_every_condition_are_returned_in_run_id_order() -> None:
    later, earlier = _run("run-b"), _run("run-a")
    skipped = _run("run-c")
    owned = {"run-a": "alpha", "run-b": "alpha", "run-c": "beta"}

    chosen = _select([later, skipped, earlier], owned=owned, held={"run-c"})

    assert chosen == (earlier, later)
