"""Live runs: date precedence and PM-precedent matching (Task 9.3, LLD D10).

One real run per case, no retries. A wrong outcome fails the test; the test is
never loosened to fit a model.
"""

from __future__ import annotations

from amoeba.runner.answering.artifacts import (
    AnswererDecline,
    CheckReply,
    ProposedAnswer,
    Verdict,
    read_answer,
    read_check,
)
from amoeba.runner.answering.inputs import QuestionInput
from live.answering.harness import AnsweringRun, LiveHarness, passage

THIS_SLICE = "140 answering-pipeline"
OTHER_SLICE = "130 web-console"

BRANCH_QUESTION = QuestionInput(THIS_SLICE, "What do we name a slice branch?")
NEW_BRANCH_RULE = passage(
    2,
    "rule",
    "2026-10-15T00:00:00Z",
    "A slice branch is named `slice/{name}`, with no index. This replaces the "
    "older `{index}-slice.{name}` form.",
    source="docs/branches.md",
)
PM_BRANCH_ANSWER = passage(
    2,
    "pm_answer",
    "2026-10-15T00:00:00Z",
    "A slice branch is named `slice/{name}`, with no index.",
    question="What do we name a slice branch?",
    slice_label=THIS_SLICE,
)
STALE_PM_BRANCH_ANSWER = passage(
    1,
    "pm_answer",
    "2026-08-01T00:00:00Z",
    "A slice branch is named `{index}-slice.{name}`.",
    question="What do we name a slice branch?",
    slice_label=THIS_SLICE,
)


def _run(
    harness: LiveHarness, name: str, question: QuestionInput, passages: str
) -> AnsweringRun:
    result = harness.run(name, question, passages)
    assert result.succeeded, result.report
    return result


def _verdict(result: AnsweringRun) -> Verdict:
    check = read_check(result.directory)
    assert isinstance(check, CheckReply), check
    return check.verdict


def test_pm_answer_dated_after_the_rule_passes_the_check(
    live_harness: LiveHarness,
) -> None:
    passages = passage(
        1,
        "rule",
        "2026-08-01T00:00:00Z",
        "A slice branch is named `{index}-slice.{name}`, for example `140-slice.foo`.",
        source="docs/branches.md",
    )
    passages += "\n" + PM_BRANCH_ANSWER
    result = _run(live_harness, "pm-later", BRANCH_QUESTION, passages)
    answer = read_answer(result.directory)
    assert isinstance(answer, ProposedAnswer), answer
    assert "P2" in answer.cited
    assert _verdict(result) is Verdict.YES


def test_rule_dated_after_the_pm_answer_is_never_overridden_by_it(
    live_harness: LiveHarness,
) -> None:
    passages = STALE_PM_BRANCH_ANSWER + "\n" + NEW_BRANCH_RULE
    result = _run(live_harness, "rule-later", BRANCH_QUESTION, passages)
    answer = read_answer(result.directory)
    assert isinstance(answer, ProposedAnswer), answer
    cites_stale_only = "P2" not in answer.cited
    # Citing the newer rule is right and passes; resting on the stale PM answer
    # alone must be refused by the check.
    expected = Verdict.NO if cites_stale_only else Verdict.YES
    assert _verdict(result) is expected, (answer, expected)


def test_reworded_question_for_the_same_slice_matches_the_pm_answer(
    live_harness: LiveHarness,
) -> None:
    pm = passage(
        1,
        "pm_answer",
        "2026-10-10T00:00:00Z",
        "Yes. Use ISO 8601 in UTC.",
        question="Should every log line carry a timestamp?",
        slice_label=THIS_SLICE,
    )
    question = QuestionInput(THIS_SLICE, "Do we want a time on each line we log?")
    result = _run(live_harness, "reworded", question, pm)
    answer = read_answer(result.directory)
    assert isinstance(answer, ProposedAnswer), answer
    assert "P1" in answer.cited
    assert _verdict(result) is Verdict.YES


def test_same_wording_for_another_slice_is_not_taken_from_the_pm_answer(
    live_harness: LiveHarness,
) -> None:
    pm = passage(
        1,
        "pm_answer",
        "2026-10-10T00:00:00Z",
        "Port 8080. It is reserved for the web console only; every other slice "
        "gets its own port and must not use 8080.",
        question="Which port does the dev server listen on?",
        slice_label=OTHER_SLICE,
    )
    question = QuestionInput(THIS_SLICE, "Which port does the dev server listen on?")
    result = _run(live_harness, "other-slice", question, pm)
    answer = read_answer(result.directory)
    if isinstance(answer, AnswererDecline):
        return
    assert isinstance(answer, ProposedAnswer), answer
    assert _verdict(result) is Verdict.NO, answer
