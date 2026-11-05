"""Mapping between program store rows and their records.

Rows arrive positionally in the column order declared by ``sql_program``, and a
row that cannot be mapped raises rather than yielding a partially-populated
object, as in ``mapping_inbox.py``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum

from amoeba.store import sql_program
from amoeba.store.inbox_models import SubmissionOutcome
from amoeba.store.mapping_journal import decode_mapping, decode_timestamp
from amoeba.store.models import UnknownVocabularyValueError
from amoeba.store.program_models import (
    ConsumptionMode,
    Member,
    Program,
    ProgramSubmissionKind,
    ProgramSubmissionRecord,
)
from amoeba.store.row_values import integer, optional_text, text


def _vocabulary[VocabularyT: StrEnum](
    value: object, vocabulary: type[VocabularyT], column: str
) -> VocabularyT:
    """Coerce a stored value into a closed program vocabulary, or raise."""
    try:
        return vocabulary(text(value, column))
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised so
        # the caller never receives a defaulted record.
        raise UnknownVocabularyValueError(
            f"{column} value {value!r} is not a valid {vocabulary.__name__}"
        ) from error


def _timestamp(value: object, column: str) -> datetime:
    decoded = decode_timestamp(value, column)
    if decoded is None:
        raise UnknownVocabularyValueError(f"{column} is NULL")
    return decoded


def _require_width(row: Sequence[object], columns: tuple[str, ...], table: str) -> None:
    if len(row) != len(columns):
        raise UnknownVocabularyValueError(
            f"{table} row has {len(row)} columns, expected {len(columns)}"
        )


def map_program(row: Sequence[object]) -> Program:
    """Map one ``programs`` row."""
    _require_width(row, sql_program.PROGRAM_COLUMNS, sql_program.TABLE_PROGRAMS)
    return Program(
        program_id=text(row[0], "program_id"),
        concept_member=text(row[1], "concept_member"),
        concept_path=text(row[2], "concept_path"),
        registered_at=_timestamp(row[3], "registered_at"),
        updated_at=_timestamp(row[4], "updated_at"),
    )


def map_member(
    row: Sequence[object], overrides: Mapping[str, ConsumptionMode]
) -> Member:
    """Map one ``program_members`` row, carrying its already-read overrides."""
    _require_width(row, sql_program.MEMBER_COLUMNS, sql_program.TABLE_PROGRAM_MEMBERS)
    return Member(
        program_id=text(row[0], "program_id"),
        project_id=text(row[1], "project_id"),
        requests_initiative=integer(row[2], "requests_initiative"),
        consumed=_vocabulary(row[3], ConsumptionMode, "consumed"),
        overrides=overrides,
        registered_at=_timestamp(row[4], "registered_at"),
        updated_at=_timestamp(row[5], "updated_at"),
    )


def map_override(row: Sequence[object]) -> tuple[str, str, ConsumptionMode]:
    """Map one ``consumption_overrides`` row to ``(provider, dependent, mode)``."""
    _require_width(
        row, sql_program.OVERRIDE_COLUMNS, sql_program.TABLE_CONSUMPTION_OVERRIDES
    )
    return (
        text(row[1], "provider_id"),
        text(row[2], "dependent_id"),
        _vocabulary(row[3], ConsumptionMode, "consumed"),
    )


def map_submission(row: Sequence[object]) -> ProgramSubmissionRecord:
    """Map one ``program_submissions`` row."""
    _require_width(
        row, sql_program.SUBMISSION_COLUMNS, sql_program.TABLE_PROGRAM_SUBMISSIONS
    )
    return ProgramSubmissionRecord(
        applied_seq=integer(row[0], "applied_seq"),
        id=text(row[1], "id"),
        kind=_vocabulary(row[2], ProgramSubmissionKind, "kind"),
        submitted_by=text(row[3], "submitted_by"),
        submitted_at=_timestamp(row[4], "submitted_at"),
        payload=decode_mapping(row[5], "payload"),
        outcome=_vocabulary(row[6], SubmissionOutcome, "outcome"),
        reason=optional_text(row[7], "reason"),
        applied_at=_timestamp(row[8], "applied_at"),
    )
