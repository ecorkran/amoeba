"""D4: the outcome map, one case per row."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from amoeba.process import RunOutcomeDocument
from amoeba.runner import supervise
from amoeba.runner.faults import LaunchFailure, ResumeFailure
from amoeba.runner.observed import (
    Finished,
    LaunchFailed,
    ResumeFailed,
    RunEnded,
    RunVanished,
)
from amoeba.runner.resolutions.vocabulary import PARAM_RESUME_CAUSE, ResumeCause
from amoeba.runner.supervise import (
    RESULT_OUTCOME_DOCUMENT,
    OutcomeClass,
    classify,
    recorded_document,
    resume_count,
    resume_ready,
    step_of,
)
from amoeba.store import CommandKind, JournalEntry
from runner.gates.purity import io_use

RESETS_AT = "2026-10-29T18:00:00+00:00"


def _ended(outcome: str, **fields: Any) -> RunEnded:
    document = {"run_id": "run-20261029-p456-aaaa1111", "outcome": outcome, **fields}
    return RunEnded(RunOutcomeDocument.model_validate(document))


def _paused(kind: str | None, **checkpoint: Any) -> RunEnded:
    return _ended("paused", checkpoint={"kind": kind, "step": "design-0", **checkpoint})


def _failed(kind: str | None) -> RunEnded:
    return _ended("failed", failure={"kind": kind, "step": "design-0", "message": "m"})


@pytest.mark.parametrize(
    ("observed", "expected"),
    [
        (_ended("completed"), OutcomeClass.COMPLETED),
        (_ended("orphaned"), OutcomeClass.TRANSIENT),
        (_failed("provider_error"), OutcomeClass.TRANSIENT),
        (_failed("stall"), OutcomeClass.TRANSIENT),
        (_paused("usage_limit", resets_at=RESETS_AT), OutcomeClass.TRANSIENT),
        (_paused("agent_question", question="which?"), OutcomeClass.QUESTION),
        (_paused("agent_question"), OutcomeClass.QUESTION),
        (_paused("usage_limit"), OutcomeClass.BLOCKED),
        (_paused("loop_exhausted"), OutcomeClass.BLOCKED),
        (_paused("awaits_human"), OutcomeClass.BLOCKED),
        (_paused("interactive_checkpoint"), OutcomeClass.BLOCKED),
        (_paused("other"), OutcomeClass.BLOCKED),
        (_paused("a_kind_from_the_future"), OutcomeClass.BLOCKED),
        (_paused(None), OutcomeClass.BLOCKED),
        (_ended("paused"), OutcomeClass.BLOCKED),
        (_failed("artifact_missing"), OutcomeClass.BLOCKED),
        (_failed("cost_cap"), OutcomeClass.BLOCKED),
        (_failed("a_kind_from_the_future"), OutcomeClass.BLOCKED),
        (_failed(None), OutcomeClass.BLOCKED),
        (_ended("failed"), OutcomeClass.BLOCKED),
        (RunVanished(), OutcomeClass.BLOCKED),
        (LaunchFailed(next(iter(LaunchFailure)), 1, "tail"), OutcomeClass.BLOCKED),
        (
            ResumeFailed(next(iter(ResumeFailure)), 1, "tail", None),
            OutcomeClass.BLOCKED,
        ),
    ],
)
def test_each_observation_has_its_class(
    observed: Finished, expected: OutcomeClass
) -> None:
    assert classify(observed) is expected


@pytest.mark.parametrize(
    "outcome", ["timed_out", "not_found", "unreadable", "unknown_status"]
)
def test_an_outcome_that_is_not_an_end_state_is_refused(outcome: str) -> None:
    with pytest.raises(ValueError, match="not an end state"):
        classify(_ended(outcome))


def test_supervise_does_no_io() -> None:
    assert io_use(supervise) == []


def _entry(
    entry_id: str,
    cause: ResumeCause | None,
    stopped: RunEnded | None,
) -> JournalEntry:
    parameters: dict[str, object] = {}
    if cause is not None:
        parameters[PARAM_RESUME_CAUSE] = cause.value
    result = (
        None
        if stopped is None
        else {RESULT_OUTCOME_DOCUMENT: stopped.document.model_dump(mode="json")}
    )
    return JournalEntry(
        entry_id, "p", "n", CommandKind.SQ_RUN, parameters, result=result
    )


def _crash(step: str | None) -> RunEnded:
    failure = {"kind": "stall", "step": step} if step else None
    return _ended("failed", failure=failure)


def _chain(
    *steps_and_causes: tuple[ResumeCause | None, RunEnded | None],
) -> list[JournalEntry]:
    """Entries newest first; the first is the one being ingested (no result)."""
    return [
        _entry(f"e{index}", cause, stopped)
        for index, (cause, stopped) in enumerate(steps_and_causes)
    ]


T = ResumeCause.TRANSIENT


def test_a_fresh_launch_has_count_zero() -> None:
    assert resume_count(_chain((None, None)), "design-0") == 0


@pytest.mark.parametrize("resumes", [1, 2, 3])
def test_resumes_at_one_step_are_counted(resumes: int) -> None:
    entries = _chain(
        *[(T, None)] + [(T, _crash("design-0"))] * (resumes - 1),
        (None, _crash("design-0")),
    )

    assert resume_count(entries, "design-0") == resumes


def test_a_different_step_restarts_the_count() -> None:
    entries = _chain((T, None), (None, _crash("tasks-0")))

    assert resume_count(entries, "design-0") == 0


def test_an_orphaned_outcome_with_nothing_before_it_has_no_step() -> None:
    entries = _chain((T, None), (None, _ended("orphaned")))

    assert resume_count(entries, "design-0") == 0


def test_the_count_stops_at_an_earlier_different_step() -> None:
    entries = _chain(
        (T, None), (T, _crash("tasks-0")), (T, _crash("design-0")), (None, _crash("x"))
    )

    assert resume_count(entries, "tasks-0") == 1


def test_a_resolution_resume_restarts_the_count() -> None:
    entries = _chain(
        (T, None),
        (ResumeCause.RESOLUTION, _crash("design-0")),
        (T, _crash("design-0")),
        (None, _crash("design-0")),
    )

    assert resume_count(entries, "design-0") == 1


def test_an_orphaned_outcome_inherits_the_step_of_the_entry_before() -> None:
    orphaned = _ended("orphaned")
    entries = _chain((T, None), (T, orphaned), (T, _crash("design-0")), (None, None))

    assert resume_count(entries, "design-0") == 2


def test_an_orphaned_outcome_being_ingested_takes_the_step_it_resumed_from() -> None:
    entries = _chain((T, None), (None, _crash("design-0")))

    assert resume_count(entries, None) == 1


def test_an_entry_without_a_recorded_document_ends_the_count() -> None:
    assert resume_count(_chain((T, None), (None, None)), "design-0") == 0


def test_step_of_prefers_the_checkpoint_then_the_failure() -> None:
    assert step_of(_paused("awaits_human").document) == "design-0"
    assert step_of(_crash("tasks-0").document) == "tasks-0"
    assert step_of(_ended("orphaned").document) is None


def test_an_unparsable_recorded_document_is_unknown() -> None:
    entry = JournalEntry(
        "e", "p", "n", CommandKind.SQ_RUN, result={RESULT_OUTCOME_DOCUMENT: {"x": 1}}
    )

    assert recorded_document(entry) is None


def test_a_usage_limit_pause_is_ready_only_from_its_reset_time() -> None:
    resets_at = datetime(2026, 10, 29, 18, 0, tzinfo=UTC)
    paused = _paused("usage_limit", resets_at=resets_at.isoformat()).document

    assert not resume_ready(paused, resets_at - timedelta(seconds=1))
    assert resume_ready(paused, resets_at)
    assert resume_ready(paused, resets_at + timedelta(seconds=1))


@pytest.mark.parametrize(
    ("observed", "ready"),
    [
        (_ended("orphaned"), True),
        (_failed("stall"), True),
        (_failed("provider_error"), True),
        (_failed("cost_cap"), False),
        (_paused("agent_question"), False),
        (_ended("completed"), False),
    ],
)
def test_every_other_outcome_is_ready_if_and_only_if_transient(
    observed: RunEnded, ready: bool
) -> None:
    assert resume_ready(observed.document, datetime(2026, 1, 1, tzinfo=UTC)) is ready
