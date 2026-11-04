"""``render_need`` writes the exact ``need.md`` format of slice 180 D4."""

from __future__ import annotations

import pytest

from amoeba.runner.request_run.inputs import RequestInput, render_need


def _request(
    *,
    project: str = "alpha",
    label: str = "140 widget-api",
    index: int = 90,
    need: str = "Add a pagination cursor to the list endpoint.",
) -> RequestInput:
    return RequestInput(project, label, index, need)


def test_exact_format() -> None:
    assert render_need(_request()) == (
        "# Request\n\n"
        "requested by: alpha, slice 140 widget-api\n"
        "requests initiative: 90\n\n"
        "Add a pagination cursor to the list endpoint."
    )


def test_multi_line_need_is_verbatim() -> None:
    need = "First line.\n\nSecond paragraph.\n  indented\n"
    assert render_need(_request(need=need)).endswith("\n\n" + need)


def test_braces_and_markdown_are_preserved() -> None:
    need = "# Not a title\nUse {model} and {slice}?\n- a list item"
    assert render_need(_request(need=need)).endswith("\n\n" + need)


@pytest.mark.parametrize(
    ("request_input", "match"),
    [
        (_request(need=""), "need"),
        (_request(need="\n  "), "need"),
        (_request(index=0), "requests_index"),
        (_request(index=-3), "requests_index"),
        (_request(project=""), "asking_project_id"),
        (_request(project="  "), "asking_project_id"),
        (_request(project="al\npha"), "asking_project_id"),
        (_request(project="al\rpha"), "asking_project_id"),
        (_request(label=""), "asking_slice_label"),
        (_request(label="140\nwidget"), "asking_slice_label"),
        (_request(label="140\rwidget"), "asking_slice_label"),
    ],
)
def test_invalid_request_is_refused(request_input: RequestInput, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        render_need(request_input)
