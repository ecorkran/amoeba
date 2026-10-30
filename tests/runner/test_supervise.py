"""D4: the outcome map, one case per row."""

from __future__ import annotations

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
from amoeba.runner.supervise import OutcomeClass, classify
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
