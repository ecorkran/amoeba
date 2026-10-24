"""One link's plan read under the budget: answers, failures, cut-offs."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import OUTPUT_HEAD_CHARS
from amoeba.runner.lifecycle.plan_read import (
    NoSlicePlan,
    PlanRead,
    PlanReadCutOff,
    PlanReadFailed,
    SliceReadFailed,
    read_plan,
)
from amoeba.upstream.context_forge import CFSliceList
from runner.observe_support import Clock, Host

FIXTURES = Path(__file__).parents[2] / "fixtures" / "cf"
LINK = "cf-1"
TIMEOUT = 8.0
INITIATIVES_KEY = "list initiatives"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _slices_key(index: int) -> str:
    return f"list slices {index}"


type Answer = subprocess.CompletedProcess[str] | BaseException


def _ok(stdout: str) -> Answer:
    return subprocess.CompletedProcess([], 0, stdout, "")


def _exit(code: int, stdout: str = "", stderr: str = "") -> Answer:
    return subprocess.CompletedProcess([], code, stdout, stderr)


class PlanCf:
    """A ``cf`` runner answering by command key from canned values."""

    def __init__(self, answers: dict[str, Answer]) -> None:
        self.answers = answers
        self.calls: list[str] = []
        self.on_call: Callable[[int], None] | None = None

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        key = " ".join(argv[1:3] if argv[2] == "initiatives" else argv[1:4])
        self.calls.append(key)
        if self.on_call is not None:
            self.on_call(len(self.calls))
        answer = self.answers[key]
        if isinstance(answer, BaseException):
            raise answer
        return answer


def _standard() -> dict[str, Answer]:
    """The captured initiatives, with the captured lists for 100 and 120."""
    return {
        INITIATIVES_KEY: _ok(_fixture("list_initiatives_a.json")),
        _slices_key(100): _ok(_fixture("list_slices_100.json")),
        _slices_key(120): _ok(_fixture("list_slices_120.json")),
        _slices_key(140): _exit(1, stderr=_fixture("list_slices_error.json")),
        _slices_key(160): _exit(1, stderr=_fixture("list_slices_error.json")),
        _slices_key(180): _exit(1, stderr=_fixture("list_slices_error.json")),
        _slices_key(200): _exit(1, stderr=_fixture("list_slices_error.json")),
    }


def _budget(deadline: float = 1_000.0, clock: Clock | None = None) -> TickBudget:
    return TickBudget(deadline, Host(), (clock or Clock()).monotonic)


def _initiative_indexes() -> list[int]:
    return [entry["index"] for entry in json.loads(_fixture("list_initiatives_a.json"))]


def _answers_for_every_initiative() -> dict[str, Answer]:
    """``_standard`` plus an error document for any initiative it does not list."""
    answers = _standard()
    for index in _initiative_indexes():
        answers.setdefault(
            _slices_key(index), _exit(1, stderr=_fixture("list_slices_error.json"))
        )
    return answers


# -- a complete read -----------------------------------------------------------


def test_a_complete_read_has_every_initiative_and_each_ones_slices() -> None:
    cf = PlanCf(_answers_for_every_initiative())

    result = read_plan(LINK, {100, 120}, cf, _budget(), TIMEOUT)

    assert isinstance(result, PlanRead)
    assert [i.index for i in result.initiatives] == _initiative_indexes()
    assert isinstance(result.slices[100], CFSliceList)
    assert isinstance(result.slices[120], CFSliceList)
    assert cf.calls[0] == INITIATIVES_KEY
    assert cf.calls[1:] == [_slices_key(i) for i in _initiative_indexes()]


def test_an_initiative_without_a_plan_and_without_linked_slices_is_no_plan() -> None:
    cf = PlanCf(_answers_for_every_initiative())

    result = read_plan(LINK, {100, 120}, cf, _budget(), TIMEOUT)

    assert isinstance(result, PlanRead)
    no_plan = [i for i, got in result.slices.items() if isinstance(got, NoSlicePlan)]
    assert no_plan and 100 not in no_plan and 120 not in no_plan


def test_the_same_error_with_linked_slices_is_a_failed_slice_read() -> None:
    cf = PlanCf(_answers_for_every_initiative())

    result = read_plan(LINK, {140}, cf, _budget(), TIMEOUT)

    assert isinstance(result, PlanRead)
    failed = result.slices[140]
    assert isinstance(failed, SliceReadFailed)
    assert "list slices 140" in failed.detail


def test_the_error_document_is_recognised_on_stdout_too() -> None:
    answers = _answers_for_every_initiative()
    answers[_slices_key(140)] = _exit(1, stdout=_fixture("list_slices_error.json"))

    result = read_plan(LINK, set(), PlanCf(answers), _budget(), TIMEOUT)

    assert isinstance(result, PlanRead) and isinstance(result.slices[140], NoSlicePlan)


# -- failures at both levels ---------------------------------------------------

_FAILURES: list[tuple[str, Answer, str]] = [
    ("timeout", subprocess.TimeoutExpired("cf", TIMEOUT), "timed out"),
    ("missing-cf", FileNotFoundError("cf"), "could not run"),
    ("non-zero", _exit(3, stdout="boom"), "exited 3"),
    ("not-json", _ok("not json"), ""),
    ("empty", _ok(""), ""),
]


@pytest.mark.parametrize(
    ("answer", "words"), [f[1:] for f in _FAILURES], ids=[f[0] for f in _FAILURES]
)
def test_each_failure_kind_fails_the_initiatives_read(
    answer: Answer, words: str
) -> None:
    answers = _answers_for_every_initiative()
    answers[INITIATIVES_KEY] = answer
    cf = PlanCf(answers)

    result = read_plan(LINK, set(), cf, _budget(), TIMEOUT)

    assert isinstance(result, PlanReadFailed)
    assert "list initiatives" in result.detail and words in result.detail
    assert cf.calls == [INITIATIVES_KEY], (
        "no slice read follows a failed initiatives read"
    )


@pytest.mark.parametrize(
    ("answer", "words"), [f[1:] for f in _FAILURES], ids=[f[0] for f in _FAILURES]
)
def test_each_failure_kind_fails_only_that_initiatives_slice_read(
    answer: Answer, words: str
) -> None:
    answers = _answers_for_every_initiative()
    answers[_slices_key(120)] = answer

    result = read_plan(LINK, {120}, PlanCf(answers), _budget(), TIMEOUT)

    assert isinstance(result, PlanRead)
    failed = result.slices[120]
    assert isinstance(failed, SliceReadFailed)
    assert "list slices 120" in failed.detail and words in failed.detail
    assert isinstance(result.slices[100], CFSliceList), "other initiatives still read"


def test_an_initiatives_document_missing_a_required_field_fails_the_read() -> None:
    answers = _answers_for_every_initiative()
    answers[INITIATIVES_KEY] = _ok('[{"name": "n", "isChecked": false}]')

    result = read_plan(LINK, set(), PlanCf(answers), _budget(), TIMEOUT)

    assert isinstance(result, PlanReadFailed)


def test_a_slice_entry_missing_a_required_field_fails_that_slice_read() -> None:
    answers = _answers_for_every_initiative()
    answers[_slices_key(120)] = _ok('{"entries": [{"name": "n"}]}')

    result = read_plan(LINK, {120}, PlanCf(answers), _budget(), TIMEOUT)

    assert isinstance(result, PlanRead)
    assert isinstance(result.slices[120], SliceReadFailed)


def test_a_failure_detail_quotes_only_the_head_of_the_output() -> None:
    answers = _answers_for_every_initiative()
    answers[INITIATIVES_KEY] = _exit(1, stdout="x" * 5 * OUTPUT_HEAD_CHARS)

    result = read_plan(LINK, set(), PlanCf(answers), _budget(), TIMEOUT)

    assert isinstance(result, PlanReadFailed)
    assert len(result.detail) < 2 * OUTPUT_HEAD_CHARS


def test_a_failed_call_is_not_retried() -> None:
    answers = _answers_for_every_initiative()
    answers[_slices_key(120)] = _exit(2)
    cf = PlanCf(answers)

    read_plan(LINK, {120}, cf, _budget(), TIMEOUT)

    assert cf.calls.count(_slices_key(120)) == 1


# -- the budget ----------------------------------------------------------------


def test_nothing_starts_with_the_budget_spent() -> None:
    cf = PlanCf(_answers_for_every_initiative())

    assert (
        read_plan(LINK, set(), cf, _budget(deadline=0.0), TIMEOUT) == PlanReadCutOff()
    )
    assert cf.calls == []


@pytest.mark.parametrize("allowed_calls", [1, 2, 3])
def test_a_cut_off_after_any_call_returns_only_the_cut_off(allowed_calls: int) -> None:
    clock = Clock()
    cf = PlanCf(_answers_for_every_initiative())

    def spend_after(count: int) -> None:
        if count == allowed_calls:
            clock.seconds = 99.0

    cf.on_call = spend_after

    result = read_plan(
        LINK, {100, 120}, cf, _budget(deadline=5.0, clock=clock), TIMEOUT
    )

    assert result == PlanReadCutOff()
    assert len(cf.calls) == allowed_calls, "a refused budget starts no further call"
