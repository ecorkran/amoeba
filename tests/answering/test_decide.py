"""``decide_answer``: every D7 check and every D8 reason it produces (slice 144)."""

from __future__ import annotations

from typing import Any

import pytest
from purity import io_use

from amoeba.answering import decide
from amoeba.answering.artifacts import (
    AnswererDecline,
    ArtifactProblem,
    CheckReply,
    ProblemKind,
    ProposedAnswer,
    Verdict,
)
from amoeba.answering.decide import (
    ARTIFACT_REASONS,
    CITATION_REASONS,
    FAILURE_REASONS,
    SOURCES_REASONS,
    Confirmed,
    Declined,
    RunSummary,
    decide_answer,
    sources_reason,
)
from amoeba.answering.passages import (
    CitationKind,
    SourcesProblem,
    SourcesProblemKind,
)
from amoeba.answering.values import AnsweringEvidence, DeclineReason
from amoeba.upstream.bounded_text import cut_to_bound
from amoeba.upstream.squadron.faults import LaunchFailure, ResumeFailure
from amoeba.upstream.squadron.launch import STDERR_TAIL_LIMIT_BYTES
from amoeba.upstream.squadron.run_outcome import (
    FailureKind,
    LaunchFailed,
    ResumeFailed,
    RunEnded,
    RunOutcomeDocument,
    RunVanished,
)

PASSAGE_IDS = frozenset({"P1", "P2"})
ANSWER = ProposedAnswer("use main", ("P1", "p2"))
YES = CheckReply(Verdict.YES, "matches P1")
NO = CheckReply(Verdict.NO, "P1 says dev")
COMPLETED = RunSummary.of(
    RunEnded(RunOutcomeDocument.model_validate({"run_id": "r", "outcome": "completed"}))
)


def _ended(outcome: str, **fields: Any) -> RunSummary:
    document = {"run_id": "r", "outcome": outcome, **fields}
    return RunSummary.of(RunEnded(RunOutcomeDocument.model_validate(document)))


def _failed(kind: str | None) -> RunSummary:
    failure = {"message": "boom"} if kind is None else {"kind": kind, "message": "boom"}
    return _ended("failed", failure=failure)


def _declined(result: Confirmed | Declined) -> Declined:
    assert isinstance(result, Declined)
    return result


def test_all_six_checks_passing_confirms_with_full_evidence() -> None:
    result = decide_answer(COMPLETED, ANSWER, YES, PASSAGE_IDS)

    assert result == Confirmed(
        "use main",
        ("P1", "p2"),
        AnsweringEvidence("use main", ("P1", "p2"), "yes", "matches P1"),
    )


@pytest.mark.parametrize(
    ("run", "reason", "detail_part"),
    [
        (_failed("provider_error"), DeclineReason.ANSWERING_RUN_FAILED, "provider"),
        (_failed("artifact_missing"), DeclineReason.ANSWERING_RUN_FAILED, "artifact"),
        (_failed("stall"), DeclineReason.ANSWERING_RUN_STALLED, "stall"),
        (_failed("cost_cap"), DeclineReason.ANSWERING_COST_CAP, "cost_cap"),
        (_failed("brand_new_kind"), DeclineReason.ANSWERING_RUN_FAILED, "brand_new"),
        (_failed(None), DeclineReason.ANSWERING_RUN_FAILED, "no failure kind"),
        (
            _ended("paused", checkpoint={"kind": "agent_question"}),
            DeclineReason.ANSWERING_RUN_FAILED,
            "agent_question",
        ),
        (_ended("orphaned"), DeclineReason.ANSWERING_RUN_ORPHANED, "orphaned"),
        (
            _ended("timed_out"),
            DeclineReason.ANSWERING_RUN_FAILED,
            "timed_out",
        ),
        (
            RunSummary.of(RunVanished()),
            DeclineReason.ANSWERING_RUN_FAILED,
            "no state",
        ),
        (
            RunSummary.of(
                LaunchFailed(LaunchFailure.EXITED_BEFORE_LINE, 1, "no such pipeline")
            ),
            DeclineReason.ANSWERING_LAUNCH_FAILED,
            "no such pipeline",
        ),
    ],
)
def test_a_run_that_did_not_complete_declines_with_its_reason(
    run: RunSummary, reason: DeclineReason, detail_part: str
) -> None:
    declined = _declined(decide_answer(run, None, None, PASSAGE_IDS))

    assert declined.reason is reason
    assert detail_part in declined.detail
    assert declined.evidence == AnsweringEvidence()


@pytest.mark.parametrize("kind", list(ProblemKind))
def test_an_answer_file_problem_declines_by_kind_and_names_the_file(
    kind: ProblemKind,
) -> None:
    problem = ArtifactProblem(kind, "answer.json: broken")

    declined = _declined(decide_answer(COMPLETED, problem, None, PASSAGE_IDS))

    assert declined.reason is ARTIFACT_REASONS[kind]
    assert "answer.json" in declined.detail
    assert declined.evidence == AnsweringEvidence()


@pytest.mark.parametrize("kind", list(ProblemKind))
def test_a_check_file_problem_declines_and_keeps_the_proposed_answer(
    kind: ProblemKind,
) -> None:
    problem = ArtifactProblem(kind, "check.json: broken")

    declined = _declined(decide_answer(COMPLETED, ANSWER, problem, PASSAGE_IDS))

    assert declined.reason is ARTIFACT_REASONS[kind]
    assert "check.json" in declined.detail
    assert declined.evidence == AnsweringEvidence("use main", ("P1", "p2"))


def test_an_answerer_decline_wins_even_when_the_check_said_yes() -> None:
    reply = AnswererDecline("the rules do not say")

    declined = _declined(decide_answer(COMPLETED, reply, YES, PASSAGE_IDS))

    assert declined.reason is DeclineReason.ANSWERER_DECLINED
    assert declined.detail == "the rules do not say"
    assert declined.evidence == AnsweringEvidence()


def test_an_answer_citing_nothing_is_uncited() -> None:
    declined = _declined(
        decide_answer(COMPLETED, ProposedAnswer("x", ()), YES, PASSAGE_IDS)
    )

    assert declined.reason is DeclineReason.UNCITED
    assert declined.evidence == AnsweringEvidence("x", ())


def test_an_answer_citing_an_unoffered_passage_names_the_ids() -> None:
    reply = ProposedAnswer("x", ("P1", "P9", "P8"))

    declined = _declined(decide_answer(COMPLETED, reply, YES, PASSAGE_IDS))

    assert declined.reason is DeclineReason.UNKNOWN_CITATION
    assert "P9, P8" in declined.detail
    assert declined.evidence == AnsweringEvidence("x", ("P1", "P9", "P8"))


def test_the_citation_check_comes_before_the_check_reply() -> None:
    declined = _declined(
        decide_answer(COMPLETED, ProposedAnswer("x", ("P9",)), None, PASSAGE_IDS)
    )

    assert declined.reason is DeclineReason.UNKNOWN_CITATION


def test_a_check_saying_no_declines_with_the_checks_reason_and_all_evidence() -> None:
    declined = _declined(decide_answer(COMPLETED, ANSWER, NO, PASSAGE_IDS))

    assert declined.reason is DeclineReason.CHECK_SAID_NO
    assert declined.detail == "P1 says dev"
    assert declined.evidence == AnsweringEvidence(
        "use main", ("P1", "p2"), "no", "P1 says dev"
    )


def test_a_check_saying_no_without_a_reason_still_has_a_detail() -> None:
    declined = _declined(
        decide_answer(COMPLETED, ANSWER, CheckReply(Verdict.NO, None), PASSAGE_IDS)
    )

    assert declined.detail


def test_a_detail_is_cut_to_the_bound() -> None:
    long_reason = "r" * (STDERR_TAIL_LIMIT_BYTES * 2)

    declined = _declined(
        decide_answer(COMPLETED, AnswererDecline(long_reason), None, PASSAGE_IDS)
    )

    assert declined.detail == cut_to_bound(long_reason)
    assert len(declined.detail.encode()) == STDERR_TAIL_LIMIT_BYTES


def test_a_completed_run_without_its_replies_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="answer reply"):
        decide_answer(COMPLETED, None, None, PASSAGE_IDS)
    with pytest.raises(ValueError, match="check reply"):
        decide_answer(COMPLETED, ANSWER, None, PASSAGE_IDS)


def test_a_failed_resume_is_a_programming_error() -> None:
    resume = ResumeFailed(ResumeFailure.REFUSED, 1, "", None)

    with pytest.raises(ValueError, match="never resumed"):
        RunSummary.of(resume)


def test_each_map_covers_its_whole_vocabulary() -> None:
    assert set(FAILURE_REASONS) == set(FailureKind)
    assert set(ARTIFACT_REASONS) == set(ProblemKind)
    assert set(CITATION_REASONS) == set(CitationKind)
    assert set(SOURCES_REASONS) == set(SourcesProblemKind)


@pytest.mark.parametrize("kind", list(SourcesProblemKind))
def test_a_sources_problem_maps_to_the_reason_of_the_same_name(
    kind: SourcesProblemKind,
) -> None:
    assert sources_reason(SourcesProblem(kind, "x")).value == kind.value


def test_decide_does_no_io() -> None:
    assert io_use(decide) == []
