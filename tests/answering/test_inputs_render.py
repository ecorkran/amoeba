"""``render_question`` writes the exact ``question.md`` format of slice 140 D3."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from amoeba.answering.inputs import (
    NO_ITEM_BARRED_TEXT,
    QuestionInput,
    render_not_authorized,
    render_question,
)


def test_exact_format() -> None:
    rendered = render_question(
        QuestionInput("140 answering-pipeline", "Which base branch?")
    )
    assert (
        rendered == "# Question\n\nslice: 140 answering-pipeline\n\nWhich base branch?"
    )


def test_multi_line_question_is_verbatim() -> None:
    text = "First line.\n\nSecond paragraph.\n  indented\n"
    rendered = render_question(QuestionInput("140 x", text))
    assert rendered.endswith("\n\n" + text)


def test_braces_and_headings_are_preserved() -> None:
    text = "# Not a title\nUse {model} and {slice}?"
    rendered = render_question(QuestionInput("140 x", text))
    assert rendered == f"# Question\n\nslice: 140 x\n\n{text}"


def test_empty_slice_label_is_refused() -> None:
    with pytest.raises(ValueError, match="slice_label"):
        render_question(QuestionInput("", "q"))


def test_empty_question_is_refused() -> None:
    with pytest.raises(ValueError, match="question"):
        render_question(QuestionInput("140 x", ""))


@pytest.mark.parametrize(
    ("label", "text", "match"),
    [
        (" ", "q", "slice_label"),
        ("140\nx", "q", "slice_label"),
        ("140\rx", "q", "slice_label"),
        ("140 x", "\n ", "question"),
    ],
)
def test_blank_or_multiline_input_is_refused(label: str, text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        render_question(QuestionInput(label, text))


@dataclass(frozen=True)
class _Item:
    key: str
    description: str


def test_not_authorized_renders_one_bullet_per_item_in_order() -> None:
    rendered = render_not_authorized(
        [_Item("push", "pushing to a remote"), _Item("release", "tagging a release")]
    )

    assert rendered == "- push: pushing to a remote\n- release: tagging a release"


def test_an_empty_not_authorized_list_says_nothing_is_barred() -> None:
    assert render_not_authorized([]) == NO_ITEM_BARRED_TEXT
    assert NO_ITEM_BARRED_TEXT == "No item is barred for this repository."
