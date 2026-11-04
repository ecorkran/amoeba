"""``prepare_request_directory`` writes only ``need.md`` (slice 180 D4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.runner.request_run.inputs import (
    RequestInput,
    prepare_request_directory,
    render_need,
)

REQUEST = RequestInput("alpha", "140 widget-api", 90, "Café need — verbatim.\r\nTwo.")


def _listing(directory: Path) -> list[str]:
    return sorted(entry.name for entry in directory.iterdir())


def test_writes_only_need_md(tmp_path: Path) -> None:
    prepare_request_directory(tmp_path, REQUEST)
    assert _listing(tmp_path) == ["need.md"]
    # Byte-for-byte: no newline translation, so the need's CRLF survives.
    assert (tmp_path / "need.md").read_bytes() == render_need(REQUEST).encode("utf-8")


def test_missing_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        prepare_request_directory(tmp_path / "absent", REQUEST)


def test_non_empty_directory_is_refused_and_unchanged(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("x")
    with pytest.raises(ValueError, match="not empty"):
        prepare_request_directory(tmp_path, REQUEST)
    assert _listing(tmp_path) == ["keep.txt"]


@pytest.mark.parametrize(
    ("request_input", "match"),
    [
        (RequestInput("alpha", "140 x", 90, " "), "need"),
        (RequestInput("alpha", "140 x", 0, "need"), "requests_index"),
        (RequestInput("a\nb", "140 x", 90, "need"), "asking_project_id"),
        (RequestInput("alpha", "", 90, "need"), "asking_slice_label"),
    ],
)
def test_invalid_request_is_refused_and_unchanged(
    tmp_path: Path, request_input: RequestInput, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        prepare_request_directory(tmp_path, request_input)
    assert _listing(tmp_path) == []
