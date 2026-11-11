"""``decisions``: the answers recorded since the PM's marker or a given time
(slice 224, D5).

The request is validated here from a raw document, so the CLI and the MCP layer pass
their input through unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    StringConstraints,
    ValidationError,
    field_validator,
)

from amoeba.answering.values import AnsweredBy, PassageRef
from amoeba.operations.decisions_models import (
    AnswererBasis,
    CitedPassage,
    DecisionsOutcome,
    DecisionsRecord,
    DecisionsResult,
    MemberName,
    PmBasis,
    ResumeRecord,
)
from amoeba.operations.deps import Deps
from amoeba.operations.members import ContextForgeError
from amoeba.operations.reject_codes import (
    RejectCode,
    unknown_program_problem,
    validation_problems,
)
from amoeba.store.decisions import DecisionRow, answers_since, read_marker
from amoeba.store.errors import StoreRowError
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.projects import ProjectNames

__all__ = [
    "DecisionsOutcome",
    "DecisionsRecord",
    "DecisionsRequest",
    "DecisionsResult",
    "decisions",
]

#: The ``kind`` of a passage that is a PM's earlier answer.
_PM_ANSWER_KIND = "pm_answer"

#: A stripped, non-empty string.
_NonBlank = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)]


class DecisionsRequest(BaseModel):
    """What ``decisions`` is asked. Without ``since`` the listing starts after the
    marker; ``program`` narrows it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: ISO-8601 with a UTC offset in; the store's UTC text once validated.
    since: StrictStr | None = None
    program: _NonBlank | None = None

    @field_validator("since")
    @classmethod
    def _utc_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            moment = datetime.fromisoformat(value.strip())
        except ValueError as error:
            raise ValueError(f"not an ISO-8601 time: {value!r}") from error
        if moment.tzinfo is None:
            raise ValueError(f"has no UTC offset: {value!r}")
        return encode_timestamp(moment)


def decisions(store: Store, document: object, *, deps: Deps) -> DecisionsResult:
    """The recorded answers ``document`` asks for, oldest first.

    Raises:
        ContextForgeError: ``cf`` gave no names, or none for a listed member.
        StoreError: The store cannot be used.
    """
    try:
        request = DecisionsRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(RejectCode.MALFORMED, validation_problems(error))
    # One read transaction, closed before ``cf`` is asked for names.
    with store.read() as transaction:
        if request.program is not None:
            unknown = unknown_program_problem(transaction, request.program)
            if unknown is not None:
                return _rejected(RejectCode.UNKNOWN_PROGRAM, (unknown,))
        marker = read_marker(transaction)
        rows = answers_since(
            transaction,
            after_seq=marker if request.since is None else None,
            since=request.since,
            program=request.program,
        )
    names = _names_for(rows, deps)
    records = tuple(_record(row, names) for row in rows)
    started_at_marker = request.since is None and request.program is None
    return DecisionsResult(
        outcome=DecisionsOutcome.LISTED,
        records=records,
        read_through=records[-1].seq if records and started_at_marker else None,
        marker=marker,
    )


def _rejected(code: RejectCode, problems: tuple[str, ...]) -> DecisionsResult:
    return DecisionsResult(
        outcome=DecisionsOutcome.REJECTED, rejection=code, problems=problems
    )


def _names_for(rows: tuple[DecisionRow, ...], deps: Deps) -> ProjectNames:
    """Names of the listed members, from one ``cf`` call; none is asked for when
    there is nothing to show."""
    if not rows:
        return {}
    names = deps.project_names()
    if isinstance(names, CfCallFailed):
        raise ContextForgeError(names.detail)
    return names


def _record(row: DecisionRow, names: ProjectNames) -> DecisionsRecord:
    answer, question = row.answer, row.question
    name = names.get(question.member_id)
    if name is None:
        raise ContextForgeError(
            f"Context Forge lists no project {question.member_id!r}, "
            f"the member of run {question.key.run_id}"
        )
    return DecisionsRecord(
        seq=answer.seq,
        recorded_at=answer.recorded_at,
        program=row.program_id,
        member=MemberName(id=question.member_id, name=name),
        run_id=question.key.run_id,
        paused_at=question.key.paused_at,
        slice_label=question.slice_label,
        question=question.question,
        answered_by=answer.answered_by,
        answer=answer.answer,
        prior_answer_seq=row.prior_answer_seq,
        based_on=_basis(row),
        resume=ResumeRecord(
            outcome=answer.resume_outcome,
            detail=answer.resume_detail,
            at=answer.resume_at,
        ),
    )


def _basis(row: DecisionRow) -> AnswererBasis | PmBasis | None:
    question = row.question
    if row.answer.answered_by is AnsweredBy.PM:
        if question.waiting_reason is None:
            return None
        return PmBasis(
            waiting_reason=question.waiting_reason,
            waiting_detail=question.waiting_detail,
        )
    evidence = question.evidence
    return AnswererBasis(
        cited=_cited(row),
        check_verdict=None if evidence is None else evidence.verdict,
        check_reason=None if evidence is None else evidence.reason,
    )


def _cited(row: DecisionRow) -> tuple[CitedPassage, ...]:
    cited_ids = row.answer.cited or ()
    offered: dict[str, PassageRef] = {
        ref.id: ref for ref in row.question.passages or ()
    }
    passages: list[CitedPassage] = []
    for passage_id in cited_ids:
        ref = offered.get(passage_id)
        if ref is None:
            raise StoreRowError(
                f"answer {row.answer.seq} cites {passage_id!r}, which the "
                f"question's passages do not hold"
            )
        passages.append(
            CitedPassage(
                id=ref.id,
                kind=None if ref.question_id is None else _PM_ANSWER_KIND,
                source=ref.source,
                date=ref.date,
            )
        )
    return tuple(passages)
