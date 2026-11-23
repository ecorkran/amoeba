"""``decisions``: the answers recorded since the PM's marker or a given time
(slice 224, D5).

The request is validated here from a raw document, so the CLI and the MCP layer pass
their input through unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    ValidationError,
    field_validator,
)

from amoeba.answering.passages import PassageKind, normalized_citations
from amoeba.answering.standing_passages import is_standing_source
from amoeba.answering.values import AnsweredBy, PassageRef
from amoeba.config.user_config import NonBlank
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
from amoeba.operations.members import ContextForgeError
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.reject_codes import (
    RejectCode,
    unknown_program_problem,
    validation_problems,
)
from amoeba.operations.since import parse_since
from amoeba.store.decisions import DecisionRow, answers_since, read_marker
from amoeba.store.errors import StoreRowError
from amoeba.store.store import Store

#: Gives each member id the name to show for it. Handed the ids of the members the
#: listing holds (never asked when it is empty). The local way reads Context Forge's
#: names; the hub names a member by its id until 261 (260 D11).
type NamesReader = Callable[[tuple[str, ...]], Mapping[str, str]]

__all__ = [
    "DecisionsOutcome",
    "DecisionsRecord",
    "DecisionsRequest",
    "DecisionsResult",
    "NamesReader",
    "decisions",
]


class DecisionsRequest(BaseModel):
    """What ``decisions`` is asked. Without ``since`` the listing starts after the
    marker; ``program`` narrows it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: ISO-8601 with a UTC offset in; the store's UTC text once validated.
    since: StrictStr | None = None
    program: NonBlank | None = None

    @field_validator("since")
    @classmethod
    def _utc_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return parse_since(value)


def decisions(store: Store, document: object, *, names: NamesReader) -> DecisionsResult:
    """The recorded answers ``document`` asks for, oldest first.

    Raises:
        ContextForgeError: ``names`` found none for a listed member (the local reader
            also raises it when ``cf`` fails).
        StoreError: The store cannot be used.
    """
    try:
        request = DecisionsRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(RejectCode.MALFORMED, validation_problems(error))
    # One read transaction, closed before ``names`` is asked (it may run ``cf``).
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
    named = _names_for(rows, names)
    records = tuple(_record(row, named) for row in rows)
    started_at_marker = request.since is None and request.program is None
    return DecisionsResult(
        outcome=DecisionsOutcome.LISTED,
        notice=(
            QUOTED_DATA_NOTICE
            if any(record.request_id is not None for record in records)
            else None
        ),
        records=records,
        read_through=records[-1].seq if records and started_at_marker else None,
        marker=marker,
    )


def _rejected(code: RejectCode, problems: tuple[str, ...]) -> DecisionsResult:
    return DecisionsResult(
        outcome=DecisionsOutcome.REJECTED, rejection=code, problems=problems
    )


def _names_for(rows: tuple[DecisionRow, ...], names: NamesReader) -> Mapping[str, str]:
    """Names of the listed members; none is asked for when there is nothing to show."""
    if not rows:
        return {}
    return names(tuple(dict.fromkeys(row.question.member_id for row in rows)))


def _record(row: DecisionRow, names: Mapping[str, str]) -> DecisionsRecord:
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
        via=answer.via,
        answer=answer.answer,
        prior_answer_seq=row.prior_answer_seq,
        based_on=_basis(row),
        resume=ResumeRecord(
            outcome=answer.resume_outcome,
            detail=answer.resume_detail,
            at=answer.resume_at,
        ),
        retracted_at=answer.retracted_at,
        retract_reason=answer.retract_reason,
        request_id=question.request_id,
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


def _cited_kind(ref: PassageRef) -> str | None:
    """The kind a stored passage record shows, which holds no kind of its own.

    A PM answer carries its question id; a standing answer's source is exactly
    ``standing:<id>`` (230). Every other kind is null rather than guessed.
    """
    if ref.question_id is not None:
        return PassageKind.PM_ANSWER.value
    if is_standing_source(ref.source):
        return PassageKind.STANDING_ANSWER.value
    return None


def _cited(row: DecisionRow) -> tuple[CitedPassage, ...]:
    # The gate accepted the ids as ``normalized_citations`` reads them, while the
    # answer row keeps them as written, so they are matched the same way.
    offered: dict[str, PassageRef] = {
        ref.id.strip().upper(): ref for ref in row.question.passages or ()
    }
    passages: list[CitedPassage] = []
    for passage_id in dict.fromkeys(normalized_citations(row.answer.cited or ())):
        ref = offered.get(passage_id)
        if ref is None:
            raise StoreRowError(
                f"answer {row.answer.seq} cites {passage_id!r}, which the "
                f"question's passages do not hold"
            )
        passages.append(
            CitedPassage(
                id=ref.id,
                kind=_cited_kind(ref),
                source=ref.source,
                date=ref.date,
            )
        )
    return tuple(passages)
