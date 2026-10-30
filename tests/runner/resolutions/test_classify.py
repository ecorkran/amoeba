"""``classify``: every D2 row, and the order the rows are tested in."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from amoeba.runner.finish import RESULT_RESUME_FAILURE
from amoeba.runner.ingest.record import RESULT_OUTCOME
from amoeba.runner.lifecycle.steps import Executor
from amoeba.runner.resolutions.classify import classify
from amoeba.runner.resolutions.vocabulary import Situation
from amoeba.store import CommandKind, JournalEntry, JournalOutcome, JournalResolver


def _entry(
    kind: CommandKind = CommandKind.SQ_RUN,
    *,
    outcome: JournalOutcome | None = JournalOutcome.COMPLETED,
    result: Mapping[str, object] | None = None,
    awaits_routing: bool = False,
    resolved_by: JournalResolver | None = JournalResolver.ISSUER,
) -> JournalEntry:
    return JournalEntry(
        id="e",
        project_id="p",
        node_id="n",
        kind=kind,
        outcome=outcome,
        result=result,
        awaits_routing=awaits_routing,
        resolved_by=resolved_by if outcome is not None else None,
    )


def _run(outcome: str | None, **extra: object) -> JournalEntry:
    result: dict[str, object] = dict(extra)
    if outcome is not None:
        result[RESULT_OUTCOME] = outcome
    return _entry(result=result)


PIPELINE = Executor.PIPELINE


@pytest.mark.parametrize(
    ("executor", "entries", "expected"),
    [
        (PIPELINE, [], Situation.BEFORE_RUN),
        (PIPELINE, [_entry(CommandKind.CF_WRITE)], Situation.BEFORE_RUN),
        (PIPELINE, [_run("paused")], Situation.PAUSED_RUN),
        (PIPELINE, [_run("completed")], Situation.COMPLETED_OUTCOME),
        (PIPELINE, [_run("failed")], Situation.ENDED_RUN),
        (PIPELINE, [_run("orphaned")], Situation.ENDED_RUN),
        (PIPELINE, [_run("vanished")], Situation.ENDED_RUN),
        (PIPELINE, [_run(None)], Situation.ENDED_RUN),
        (
            PIPELINE,
            [_entry(result={RESULT_RESUME_FAILURE: "spawn_error"})],
            Situation.ENDED_RUN,
        ),
        (PIPELINE, [_entry(outcome=None)], Situation.UNRESOLVABLE),
        (None, [], Situation.NO_DECISION),
        (Executor.HUMAN, [], Situation.NO_DECISION),
    ],
)
def test_each_row(
    executor: Executor | None, entries: list[JournalEntry], expected: Situation
) -> None:
    assert classify(executor, entries) is expected


def test_the_latest_entry_decides_not_an_older_one() -> None:
    entries = [_run("paused"), _entry(CommandKind.CF_WRITE)]

    assert classify(PIPELINE, entries) is Situation.BEFORE_RUN


def test_unresolvable_wins_over_a_human_step() -> None:
    assert classify(Executor.HUMAN, [_entry(outcome=None)]) is Situation.UNRESOLVABLE


def test_a_failed_resume_stays_a_paused_run() -> None:
    """Outcome stays ``paused`` with ``resume_failure``, so ``rerun`` is not offered."""
    failed = _run("paused", **{RESULT_RESUME_FAILURE: "refused"})

    assert classify(PIPELINE, [failed]) is Situation.PAUSED_RUN


def test_a_resume_with_a_missing_run_is_an_ended_run() -> None:
    missing = _run("not_found", **{RESULT_RESUME_FAILURE: "run_missing"})

    assert classify(PIPELINE, [missing]) is Situation.ENDED_RUN


def test_a_recovery_resolved_entry_is_an_ended_run() -> None:
    recovered = _entry(
        outcome=JournalOutcome.NOT_APPLIED, resolved_by=JournalResolver.RECOVERY
    )

    assert classify(PIPELINE, [recovered]) is Situation.ENDED_RUN
