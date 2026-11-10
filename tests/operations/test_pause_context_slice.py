"""``resolve_slice`` against the recorded plan reads (slice 223, task 4.3)."""

from __future__ import annotations

from pathlib import Path

from cf_plan_run import plan_cf_run

from amoeba.answering.passages import SourcesProblem, SourcesProblemKind
from amoeba.answering.source_reads import SliceRef
from amoeba.operations.pause_context import (
    NO_SLICE_LABEL,
    SliceContext,
    resolve_slice,
)

CHECKOUT = Path("/work/checkout")
PROJECT_ID = "cf-project"
#: Slice 223 is in initiative 220's plan; 299 is in none (see the fixtures README).
IN_PLAN = "223"
IN_NO_PLAN = "299"


def _resolve(params: dict[str, str], *, broken: bool = False) -> object:
    run = plan_cf_run(integration_branch="", broken=broken)
    return resolve_slice(CHECKOUT, PROJECT_ID, params, run)


def test_a_slice_in_a_plan_gets_its_label_and_initiative() -> None:
    result = _resolve({"slice": IN_PLAN})

    assert result == SliceContext("223 Pause Handling", SliceRef(223, 220))


def test_the_nearest_lower_initiative_is_searched_first() -> None:
    run = plan_cf_run(integration_branch="", broken=False)

    resolve_slice(CHECKOUT, PROJECT_ID, {"slice": IN_PLAN}, run)

    slices_calls = [call[3] for call in run.calls if call[1:3] == ["list", "slices"]]
    assert slices_calls == ["220"]


def test_a_slice_in_no_plan_is_sources_missing_after_every_candidate_is_tried() -> None:
    run = plan_cf_run(integration_branch="", broken=False)

    result = resolve_slice(CHECKOUT, PROJECT_ID, {"slice": IN_NO_PLAN}, run)

    assert isinstance(result, SourcesProblem)
    assert result.kind is SourcesProblemKind.MISSING
    slices_calls = [call[3] for call in run.calls if call[1:3] == ["list", "slices"]]
    assert slices_calls == ["220", "200", "180", "160", "140", "120", "100"]


def test_a_non_integer_parameter_is_sources_missing_and_asks_cf_nothing() -> None:
    run = plan_cf_run(integration_branch="", broken=False)

    result = resolve_slice(CHECKOUT, PROJECT_ID, {"slice": "two-two-three"}, run)

    assert isinstance(result, SourcesProblem)
    assert result.kind is SourcesProblemKind.MISSING
    assert "two-two-three" in result.detail
    assert run.calls == []


def test_no_parameter_is_the_no_slice_context() -> None:
    run = plan_cf_run(integration_branch="", broken=False)

    result = resolve_slice(CHECKOUT, PROJECT_ID, {"model": "haiku"}, run)

    assert result == SliceContext(NO_SLICE_LABEL, None)
    assert run.calls == []


def test_a_failing_cf_is_sources_unreadable_with_the_output_head() -> None:
    result = _resolve({"slice": IN_PLAN}, broken=True)

    assert isinstance(result, SourcesProblem)
    assert result.kind is SourcesProblemKind.UNREADABLE
    assert "simulated failure" in result.detail
