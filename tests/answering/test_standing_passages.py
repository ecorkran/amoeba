"""The ``standing_answer`` passages (slice 230, D5)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from amoeba.answering.passage_types import Passage, PassageKind
from amoeba.answering.passages import PassageSet, render_passages
from amoeba.answering.standing_passages import (
    STANDING_SOURCE_PREFIX,
    StandingAnswer,
    add_standing_passages,
    is_standing_source,
    standing_passage,
    too_large_detail,
)

GIVEN = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
RULING = StandingAnswer(
    standing_id=7, text="Fixture versions are never bumped.\n", given_at=GIVEN
)
RULE = Passage(
    id="P1", kind=PassageKind.RULE, source="CLAUDE.md", date=GIVEN, text="rule\n",
    question=None, slice_label=None, question_id=None, member=None,
)  # fmt: skip


def test_the_passage_carries_the_kind_source_date_and_text_only() -> None:
    passage = standing_passage(RULING, 3)

    assert (passage.id, passage.kind, passage.source, passage.date, passage.text) == (
        "P3",
        PassageKind.STANDING_ANSWER,
        f"{STANDING_SOURCE_PREFIX}7",
        GIVEN,
        RULING.text,
    )
    assert (passage.question, passage.slice_label, passage.question_id) == (
        None,
        None,
        None,
    )
    assert passage.member is None


def test_the_rendered_passage_has_no_question_or_slice_line() -> None:
    rendered = render_passages(PassageSet((standing_passage(RULING, 1),), "c", ()))

    lines = rendered.splitlines()
    assert "kind: standing_answer" in lines
    assert "source: standing:7" in lines
    assert "date: 2026-11-20T12:00:00Z" in lines
    assert not any(line.startswith(("question:", "slice:")) for line in lines)
    assert rendered.endswith(RULING.text)


def test_numbering_follows_the_kept_passages_in_id_order() -> None:
    later = StandingAnswer(standing_id=9, text="later", given_at=GIVEN)
    earlier = StandingAnswer(standing_id=2, text="earlier", given_at=GIVEN)

    passages = add_standing_passages([RULE], [later, earlier])

    assert [(p.id, p.source) for p in passages] == [
        ("P1", "CLAUDE.md"),
        ("P2", "standing:2"),
        ("P3", "standing:9"),
    ]


def test_no_standing_answers_leaves_the_kept_passages() -> None:
    assert add_standing_passages([RULE], []) == [RULE]


def test_the_detail_gives_both_shares_and_the_limit() -> None:
    detail = too_large_detail(120, 45, 150)

    assert "120 characters" in detail
    assert "standing answers 45" in detail
    assert "the limit is 150" in detail


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("standing:7", True),
        ("standing:123", True),
        ("standing:", False),
        ("standing:0", False),
        ("standing:7x", False),
        ("standing:7/rules.md", False),
        ("docs/standing:7", False),
        ("CLAUDE.md", False),
    ],
)
def test_only_the_exact_standing_source_form_is_recognised(
    source: str, expected: bool
) -> None:
    assert is_standing_source(source) is expected


def test_a_built_standing_passage_source_is_recognised() -> None:
    source = standing_passage(RULING, 1).source

    assert source is not None
    assert is_standing_source(source)
