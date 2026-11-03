"""The decide function: a finished answering run becomes an answer or a decline.

Slice 144, D7 and D8.

Pure: it reads only what was recorded (the run's end, the two reply values, the
passage ids stored at launch) and returns a value. The six checks of D7 run in
order and the first failure decides. The maps from a problem to a decline reason
are defined once, here (D8); ``launch.py`` reuses :func:`sources_reason`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from amoeba.process import (
    CheckpointKind,
    FailureKind,
    RunOutcome,
    UnknownKind,
    parse_checkpoint_kind,
    parse_failure_kind,
)
from amoeba.runner.answering.artifacts import (
    AnswererDecline,
    AnswerReply,
    ArtifactProblem,
    CheckReply,
    ProblemKind,
    ProposedAnswer,
    Verdict,
)
from amoeba.runner.answering.passages import (
    CitationKind,
    SourcesProblem,
    SourcesProblemKind,
    check_citations,
)
from amoeba.runner.ingest.outcome import cut_to_bound
from amoeba.runner.observed import (
    Finished,
    LaunchFailed,
    ResumeFailed,
    RunEnded,
    RunVanished,
)
from amoeba.store import AnsweringEvidence, DeclineReason

#: Why a run ended with a ``failed`` outcome, by Squadron's failure kind. A kind
#: not in this map, or no kind, is ``answering_run_failed`` with the raw kind in
#: the detail; it is never matched to a near member.
FAILURE_REASONS: Final[Mapping[FailureKind, DeclineReason]] = MappingProxyType(
    {
        FailureKind.PROVIDER_ERROR: DeclineReason.ANSWERING_RUN_FAILED,
        FailureKind.ARTIFACT_MISSING: DeclineReason.ANSWERING_RUN_FAILED,
        FailureKind.STALL: DeclineReason.ANSWERING_RUN_STALLED,
        FailureKind.COST_CAP: DeclineReason.ANSWERING_COST_CAP,
    }
)

#: A reply file's problem, by kind.
ARTIFACT_REASONS: Final[Mapping[ProblemKind, DeclineReason]] = MappingProxyType(
    {
        ProblemKind.MISSING: DeclineReason.ARTIFACT_MISSING,
        ProblemKind.MALFORMED: DeclineReason.ARTIFACT_MALFORMED,
    }
)

#: A citation problem, by kind.
CITATION_REASONS: Final[Mapping[CitationKind, DeclineReason]] = MappingProxyType(
    {
        CitationKind.UNCITED: DeclineReason.UNCITED,
        CitationKind.UNKNOWN_IDS: DeclineReason.UNKNOWN_CITATION,
    }
)

#: A passage-assembly problem, by kind (143's ``SourcesProblemKind``, one to one).
SOURCES_REASONS: Final[Mapping[SourcesProblemKind, DeclineReason]] = MappingProxyType(
    {
        SourcesProblemKind.TOO_LARGE: DeclineReason.SOURCES_TOO_LARGE,
        SourcesProblemKind.MISSING: DeclineReason.SOURCES_MISSING,
        SourcesProblemKind.UNREADABLE: DeclineReason.SOURCES_UNREADABLE,
    }
)


class RunState(StrEnum):
    """How an answering run ended, as far as the decision cares."""

    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    ORPHANED = "orphaned"
    VANISHED = "vanished"
    LAUNCH_FAILED = "launch_failed"
    #: An outcome that is not an end state (``timed_out``, ``unknown_status``...).
    UNEXPECTED = "unexpected"


@dataclass(frozen=True)
class RunSummary:
    """The facts of a finished answering run that the decision reads."""

    state: RunState
    failure_kind: FailureKind | UnknownKind | None = None
    #: The failure message, the checkpoint kind, the launch error or the outcome.
    detail: str = ""

    @staticmethod
    def of(finished: Finished) -> RunSummary:
        """Summarise what the observer concluded.

        Raises:
            ValueError: ``finished`` is a failed resume; an answering run is never
                resumed, so one means a programming error.
        """
        match finished:
            case LaunchFailed():
                return RunSummary(RunState.LAUNCH_FAILED, detail=finished.tail)
            case RunVanished():
                return RunSummary(RunState.VANISHED, detail="the run left no state")
            case ResumeFailed():
                raise ValueError("an answering run is never resumed")
            case RunEnded():
                return _ended(finished)


def _ended(finished: RunEnded) -> RunSummary:
    document = finished.document
    match document.outcome:
        case RunOutcome.COMPLETED:
            return RunSummary(RunState.COMPLETED)
        case RunOutcome.FAILED:
            failure = document.failure
            kind = parse_failure_kind(None if failure is None else failure.kind)
            message = None if failure is None else failure.message
            return RunSummary(RunState.FAILED, kind, _failure_detail(kind, message))
        case RunOutcome.PAUSED:
            raw = None if document.checkpoint is None else document.checkpoint.kind
            return RunSummary(RunState.PAUSED, detail=_paused_detail(raw))
        case RunOutcome.ORPHANED:
            return RunSummary(RunState.ORPHANED, detail="the run was orphaned")
        case _:
            outcome = document.outcome.value
            return RunSummary(RunState.UNEXPECTED, detail=f"run outcome {outcome}")


def _failure_detail(kind: FailureKind | UnknownKind | None, message: str | None) -> str:
    named = "no failure kind" if kind is None else _kind_text(kind)
    return named if not message else f"{named}: {message}"


def _kind_text(kind: FailureKind | UnknownKind | CheckpointKind) -> str:
    return kind.raw if isinstance(kind, UnknownKind) else kind.value


def _paused_detail(raw_kind: str | None) -> str:
    kind = parse_checkpoint_kind(raw_kind)
    named = "no checkpoint kind" if kind is None else _kind_text(kind)
    return f"the run paused at a checkpoint ({named}); the pipeline has no human step"


@dataclass(frozen=True)
class Confirmed:
    """The answer passed every check."""

    answer: str
    cited: tuple[str, ...]
    evidence: AnsweringEvidence


@dataclass(frozen=True)
class Declined:
    """A question left unanswered: ``reason`` is the code, ``detail`` is for the PM."""

    reason: DeclineReason
    detail: str
    evidence: AnsweringEvidence


def sources_reason(problem: SourcesProblem) -> DeclineReason:
    """The decline reason for a passage-assembly problem."""
    return SOURCES_REASONS[problem.kind]


def decide_answer(
    run: RunSummary,
    answer: AnswerReply | ArtifactProblem | None,
    check: CheckReply | ArtifactProblem | None,
    passage_ids: Collection[str],
) -> Confirmed | Declined:
    """Apply D7's six checks in order; the first failure decides.

    ``answer`` and ``check`` are what ``read_answer`` and ``read_check`` returned,
    or ``None`` when the run did not complete and the files were not read.

    Raises:
        ValueError: The run completed but a reply the checks need was not read.
    """
    nothing = AnsweringEvidence()
    if run.state is not RunState.COMPLETED:
        return _run_decline(run, nothing)
    if answer is None:
        raise ValueError("a completed run needs its answer reply read")
    if isinstance(answer, ArtifactProblem):
        return _artifact_decline(answer, nothing)
    if isinstance(answer, AnswererDecline):
        return Declined(
            DeclineReason.ANSWERER_DECLINED, cut_to_bound(answer.reason), nothing
        )
    return _after_answer(answer, check, passage_ids)


def _after_answer(
    answer: ProposedAnswer,
    check: CheckReply | ArtifactProblem | None,
    passage_ids: Collection[str],
) -> Confirmed | Declined:
    evidence = AnsweringEvidence(proposed_answer=answer.answer, cited=answer.cited)
    citation = check_citations(answer.cited, passage_ids)
    if citation is not None:
        return Declined(
            CITATION_REASONS[citation.kind], _citation_detail(citation.ids), evidence
        )
    if check is None:
        raise ValueError("a completed run needs its check reply read")
    if isinstance(check, ArtifactProblem):
        return _artifact_decline(check, evidence)
    checked = AnsweringEvidence(
        proposed_answer=answer.answer,
        cited=answer.cited,
        verdict=check.verdict.value,
        reason=check.reason,
    )
    if check.verdict is not Verdict.YES:
        reason = check.reason or "the check said no and gave no reason"
        return Declined(DeclineReason.CHECK_SAID_NO, cut_to_bound(reason), checked)
    return Confirmed(answer.answer, answer.cited, checked)


def _run_decline(run: RunSummary, evidence: AnsweringEvidence) -> Declined:
    detail = cut_to_bound(run.detail)
    match run.state:
        case RunState.LAUNCH_FAILED:
            reason = DeclineReason.ANSWERING_LAUNCH_FAILED
        case RunState.ORPHANED:
            reason = DeclineReason.ANSWERING_RUN_ORPHANED
        case RunState.FAILED:
            reason = _failure_reason(run.failure_kind)
        case _:
            reason = DeclineReason.ANSWERING_RUN_FAILED
    return Declined(reason, detail, evidence)


def _failure_reason(kind: FailureKind | UnknownKind | None) -> DeclineReason:
    if isinstance(kind, FailureKind):
        return FAILURE_REASONS[kind]
    return DeclineReason.ANSWERING_RUN_FAILED


def _artifact_decline(
    problem: ArtifactProblem, evidence: AnsweringEvidence
) -> Declined:
    return Declined(
        ARTIFACT_REASONS[problem.kind], cut_to_bound(problem.detail), evidence
    )


def _citation_detail(ids: tuple[str, ...]) -> str:
    if not ids:
        return "the answer cites no passage"
    return f"the answer cites passages that were not offered: {', '.join(ids)}"
