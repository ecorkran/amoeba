"""One serializer and one parser per JSON column of ``questions`` and ``answers``
(slice 223, D10): ``passages``, ``evidence`` and ``cited``.

Parsers raise ``StoreRowError`` naming the column; a bad value is never an empty
one. Times are UTC ISO-8601 text, as everywhere in the store.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final

from amoeba.answering.values import AnsweringEvidence, PassageRef
from amoeba.store.errors import StoreRowError
from amoeba.store.row_values import (
    decode_mapping,
    decode_mapping_list,
    decode_string_list,
    decode_timestamp,
    encode_string_list,
    encode_timestamp,
    optional_text,
    text,
)

PASSAGES_COLUMN: Final = "questions.passages"
EVIDENCE_COLUMN: Final = "questions.evidence"
CITED_COLUMN: Final = "answers.cited"

_ID_KEY: Final = "id"
_SOURCE_KEY: Final = "source"
_QUESTION_ID_KEY: Final = "question_id"
_DATE_KEY: Final = "date"
_PROPOSED_ANSWER_KEY: Final = "proposed_answer"
_CITED_KEY: Final = "cited"
_VERDICT_KEY: Final = "verdict"
_REASON_KEY: Final = "reason"


def serialize_passages(passages: tuple[PassageRef, ...]) -> str:
    return json.dumps(
        [
            {
                _ID_KEY: passage.id,
                _SOURCE_KEY: passage.source,
                _QUESTION_ID_KEY: passage.question_id,
                _DATE_KEY: encode_timestamp(passage.date),
            }
            for passage in passages
        ]
    )


def parse_passages(value: object) -> tuple[PassageRef, ...]:
    """The passages a stored array holds, or ``StoreRowError``."""
    return tuple(
        _passage_from(item) for item in decode_mapping_list(value, PASSAGES_COLUMN)
    )


def _passage_from(fields: Mapping[str, object]) -> PassageRef:
    missing = [
        key
        for key in (_ID_KEY, _SOURCE_KEY, _QUESTION_ID_KEY, _DATE_KEY)
        if key not in fields
    ]
    if missing:
        raise StoreRowError(f"{PASSAGES_COLUMN} item lacks {missing}: {fields!r}")
    return PassageRef(
        id=text(fields[_ID_KEY], PASSAGES_COLUMN),
        source=text(fields[_SOURCE_KEY], PASSAGES_COLUMN),
        question_id=optional_text(fields[_QUESTION_ID_KEY], PASSAGES_COLUMN),
        date=decode_timestamp(fields[_DATE_KEY], PASSAGES_COLUMN),
    )


def serialize_evidence(evidence: AnsweringEvidence) -> str:
    return json.dumps(
        {
            _PROPOSED_ANSWER_KEY: evidence.proposed_answer,
            _CITED_KEY: None if evidence.cited is None else list(evidence.cited),
            _VERDICT_KEY: evidence.verdict,
            _REASON_KEY: evidence.reason,
        }
    )


def parse_evidence(value: object) -> AnsweringEvidence:
    """The evidence a stored object holds, or ``StoreRowError``."""
    fields = decode_mapping(value, EVIDENCE_COLUMN)
    missing = [
        key
        for key in (_PROPOSED_ANSWER_KEY, _CITED_KEY, _VERDICT_KEY, _REASON_KEY)
        if key not in fields
    ]
    if missing:
        raise StoreRowError(f"{EVIDENCE_COLUMN} lacks {missing}: {value!r}")
    cited = fields[_CITED_KEY]
    return AnsweringEvidence(
        proposed_answer=optional_text(fields[_PROPOSED_ANSWER_KEY], EVIDENCE_COLUMN),
        cited=(
            None
            if cited is None
            else decode_string_list(json.dumps(cited), EVIDENCE_COLUMN)
        ),
        verdict=optional_text(fields[_VERDICT_KEY], EVIDENCE_COLUMN),
        reason=optional_text(fields[_REASON_KEY], EVIDENCE_COLUMN),
    )


def serialize_cited(passage_ids: tuple[str, ...]) -> str:
    return encode_string_list(passage_ids)


def parse_cited(value: object) -> tuple[str, ...]:
    """The passage ids a stored array holds, or ``StoreRowError``."""
    return decode_string_list(value, CITED_COLUMN)
