"""``select_prunable``: each of D6's conditions, failing alone, over documents."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from amoeba.process.run_pruning import PAUSED_STATUS, PRUNE_RETENTION, select_prunable
from amoeba.process.sq_outcome import RunCheckpoint, RunOutcome, RunOutcomeDocument

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
OWNER = "alpha"
RUN_ID = "run-20261001-review-aaaa1111"
OLD_ENOUGH = NOW - PRUNE_RETENTION - timedelta(days=1)

#: Distinguishes "leave the default" from "pass None" for the nullable fields.
_DEFAULT = object()


def _document(
    run_id: str = RUN_ID,
    *,
    outcome: RunOutcome = RunOutcome.PAUSED,
    status: str | None = PAUSED_STATUS,
    paused_at: object = _DEFAULT,
    updated_at: object = _DEFAULT,
) -> RunOutcomeDocument:
    paused = OLD_ENOUGH if paused_at is _DEFAULT else paused_at
    updated = OLD_ENOUGH if updated_at is _DEFAULT else updated_at
    assert paused is None or isinstance(paused, datetime)
    assert updated is None or isinstance(updated, datetime)
    return RunOutcomeDocument(
        run_id=run_id,
        outcome=outcome,
        status=status,
        pipeline="review",
        started_at=OLD_ENOUGH,
        updated_at=updated,
        checkpoint=RunCheckpoint(paused_at=paused),
    )


def _select(
    documents: list[RunOutcomeDocument],
    *,
    owned: dict[str, str] | None = None,
    held: set[str] | None = None,
) -> tuple[RunOutcomeDocument, ...]:
    return select_prunable(
        documents,
        owned={RUN_ID: OWNER} if owned is None else owned,
        held=set() if held is None else held,
        now=NOW,
    )


def test_a_run_meeting_every_condition_is_selected() -> None:
    document = _document()

    assert _select([document]) == (document,)


def test_a_run_nobody_owns_is_never_selected() -> None:
    """Owned: runs the PM launched are not Amoeba's to prune."""
    assert _select([_document()], owned={}) == ()


def test_a_run_a_live_node_still_names_is_held() -> None:
    """Held: a resumed-but-not-done node's run is not offered."""
    assert _select([_document()], held={RUN_ID}) == ()


@pytest.mark.parametrize(
    "outcome", [outcome for outcome in RunOutcome if outcome is not RunOutcome.PAUSED]
)
def test_an_outcome_other_than_paused_is_not_selected(outcome: RunOutcome) -> None:
    assert _select([_document(outcome=outcome)]) == ()


@pytest.mark.parametrize("status", ["completed", "failed", "running", None])
def test_a_status_other_than_paused_is_not_selected(status: str | None) -> None:
    """A paused outcome with a different or unknown status is a disagreement."""
    assert _select([_document(status=status)]) == ()


def test_a_run_with_no_paused_at_is_never_selected() -> None:
    """Squadron could not report the checkpoint: unknown, not a value to guess."""
    assert _select([_document(paused_at=None)]) == ()


def test_a_run_with_no_checkpoint_at_all_is_never_selected() -> None:
    bare = RunOutcomeDocument(
        run_id=RUN_ID,
        outcome=RunOutcome.PAUSED,
        status=PAUSED_STATUS,
        updated_at=OLD_ENOUGH,
    )

    assert _select([bare]) == ()


def test_a_run_with_a_naive_paused_at_is_never_selected() -> None:
    naive = OLD_ENOUGH.replace(tzinfo=None)

    assert _select([_document(paused_at=naive)]) == ()


def test_a_run_with_no_updated_at_is_never_selected() -> None:
    assert _select([_document(updated_at=None)]) == ()


def test_a_run_with_a_naive_updated_at_is_never_selected() -> None:
    """No offset means no safe comparison with ``now``: unknown, not a crash."""
    naive = OLD_ENOUGH.replace(tzinfo=None)

    assert _select([_document(updated_at=naive)]) == ()


def test_a_run_younger_than_the_retention_is_not_selected() -> None:
    young = NOW - PRUNE_RETENTION + timedelta(seconds=1)

    assert _select([_document(updated_at=young)]) == ()


def test_a_run_exactly_at_the_retention_is_selected() -> None:
    document = _document(updated_at=NOW - PRUNE_RETENTION)

    assert _select([document]) == (document,)


def test_only_the_runs_meeting_every_condition_are_returned_in_run_id_order() -> None:
    later, earlier = _document("run-b"), _document("run-a")
    skipped = _document("run-c")
    owned = {"run-a": "alpha", "run-b": "alpha", "run-c": "beta"}

    chosen = _select([later, skipped, earlier], owned=owned, held={"run-c"})

    assert chosen == (earlier, later)
