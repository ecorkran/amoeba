"""Round-trips and bad-input behavior of the question JSON columns (slice 223, 1.4)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from amoeba.answering.values import AnsweringEvidence, PassageRef
from amoeba.store.errors import StoreRowError
from amoeba.store.question_json import (
    CITED_COLUMN,
    EVIDENCE_COLUMN,
    PASSAGES_COLUMN,
    parse_cited,
    parse_evidence,
    parse_passages,
    serialize_cited,
    serialize_evidence,
    serialize_passages,
)

MOMENT = datetime(2026, 11, 10, 12, 30, tzinfo=UTC)


def test_passages_round_trip() -> None:
    passages = (
        PassageRef(id="r1", source="CLAUDE.md", question_id=None, date=MOMENT),
        PassageRef(id="pm-4", source="answer 4", question_id="run:ts", date=MOMENT),
    )

    assert parse_passages(serialize_passages(passages)) == passages


def test_empty_passages_round_trip() -> None:
    assert parse_passages(serialize_passages(())) == ()


def test_evidence_round_trip_complete_and_partial() -> None:
    complete = AnsweringEvidence(
        proposed_answer="Use 300 lines.", cited=("r1", "r2"), verdict="yes", reason="ok"
    )
    partial = AnsweringEvidence()

    assert parse_evidence(serialize_evidence(complete)) == complete
    assert parse_evidence(serialize_evidence(partial)) == partial


def test_cited_round_trip() -> None:
    assert parse_cited(serialize_cited(("r1", "pm-4"))) == ("r1", "pm-4")


@pytest.mark.parametrize(
    ("parser", "column", "bad"),
    [
        (parse_passages, PASSAGES_COLUMN, "not json"),
        (parse_passages, PASSAGES_COLUMN, json.dumps({"id": "x"})),
        (parse_passages, PASSAGES_COLUMN, json.dumps(["x"])),
        (parse_passages, PASSAGES_COLUMN, json.dumps([{"id": "x"}])),
        (parse_passages, PASSAGES_COLUMN, None),
        (parse_evidence, EVIDENCE_COLUMN, "not json"),
        (parse_evidence, EVIDENCE_COLUMN, json.dumps(["x"])),
        (parse_evidence, EVIDENCE_COLUMN, json.dumps({"verdict": "yes"})),
        (parse_cited, CITED_COLUMN, "not json"),
        (parse_cited, CITED_COLUMN, json.dumps({"a": 1})),
        (parse_cited, CITED_COLUMN, json.dumps([1])),
    ],
)
def test_bad_input_raises_naming_the_column(
    parser: Callable[[object], object], column: str, bad: object
) -> None:
    with pytest.raises(StoreRowError, match=column):
        parser(bad)
