"""``classify``: a blocked slice is either holding a run to resume or it is not."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from amoeba.runner.finish import RESULT_RESUME_FAILURE
from amoeba.runner.resolutions.classify import classify
from amoeba.runner.resolutions.vocabulary import Situation
from amoeba.runner.supervise import RESULT_OUTCOME
from amoeba.store import CommandKind, JournalEntry, JournalOutcome, JournalResolver


def _entry(
    kind: CommandKind = CommandKind.SQ_RUN,
    *,
    outcome: JournalOutcome | None = JournalOutcome.COMPLETED,
    result: Mapping[str, object] | None = None,
    resolved_by: JournalResolver | None = JournalResolver.ISSUER,
) -> JournalEntry:
    return JournalEntry(
        id="e",
        project_id="p",
        node_id="n",
        kind=kind,
        outcome=outcome,
        result=result,
        resolved_by=resolved_by if outcome is not None else None,
    )


def _run(outcome: str | None, **extra: object) -> JournalEntry:
    result: dict[str, object] = dict(extra)
    if outcome is not None:
        result[RESULT_OUTCOME] = outcome
    return _entry(result=result)


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        ([], Situation.NO_RUN),
        ([_entry(CommandKind.CF_WRITE)], Situation.NO_RUN),
        ([_run("paused")], Situation.RUN_TO_RESUME),
        ([_run("failed")], Situation.RUN_TO_RESUME),
        ([_run("orphaned")], Situation.RUN_TO_RESUME),
        ([_run("completed")], Situation.NO_RUN),
        ([_run("vanished")], Situation.NO_RUN),
        ([_run("not_found")], Situation.NO_RUN),
        ([_run(None)], Situation.NO_RUN),
        ([_entry(result={RESULT_RESUME_FAILURE: "spawn_error"})], Situation.NO_RUN),
        ([_entry(outcome=None)], Situation.UNRESOLVABLE),
    ],
)
def test_each_row(entries: list[JournalEntry], expected: Situation) -> None:
    assert classify(entries) is expected


def test_the_latest_entry_decides_not_an_older_one() -> None:
    entries = [_run("paused"), _entry(CommandKind.CF_WRITE)]

    assert classify(entries) is Situation.NO_RUN


def test_a_failed_resume_of_a_live_run_is_still_a_run_to_resume() -> None:
    """The recorded outcome stays ``paused`` with ``resume_failure``."""
    failed = _run("paused", **{RESULT_RESUME_FAILURE: "refused"})

    assert classify([failed]) is Situation.RUN_TO_RESUME


def test_a_resume_whose_run_was_missing_has_no_run_to_resume() -> None:
    missing = _run("not_found", **{RESULT_RESUME_FAILURE: "run_missing"})

    assert classify([missing]) is Situation.NO_RUN


def test_a_recovery_resolved_entry_has_no_run_to_resume() -> None:
    recovered = _entry(
        outcome=JournalOutcome.NOT_APPLIED, resolved_by=JournalResolver.RECOVERY
    )

    assert classify([recovered]) is Situation.NO_RUN
