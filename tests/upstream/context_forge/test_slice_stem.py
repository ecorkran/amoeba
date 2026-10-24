"""``parse_slice_stem``: the one rule for a slice's index and name."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amoeba.upstream.context_forge import SliceStem, parse_slice_stem

CF_GET_FIXTURE = Path(__file__).parents[2] / "fixtures" / "cf" / "cf_get_amoeba.json"


def test_real_file_slice_value_parses() -> None:
    file_slice = json.loads(CF_GET_FIXTURE.read_bytes())["fileSlice"]
    assert parse_slice_stem(file_slice) == SliceStem(
        index=102, name="resident-process-and-recovery"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "125-slice.run-dispatch-and-outcome-ingestion",
            SliceStem(125, "run-dispatch-and-outcome-ingestion"),
        ),
        (
            "user/slices/125-slice.run-dispatch-and-outcome-ingestion.md",
            SliceStem(125, "run-dispatch-and-outcome-ingestion"),
        ),
        ("/abs/dir/7-slice.foo.md", SliceStem(7, "foo")),
        ("0125-slice.padded", SliceStem(125, "padded")),
        ("130-slice.v1.2-parser", SliceStem(130, "v1.2-parser")),
        ("130-slice.v1.2-parser.md", SliceStem(130, "v1.2-parser")),
        ("  130-slice.spaced  ", SliceStem(130, "spaced")),
    ],
)
def test_accepted_shapes(text: str, expected: SliceStem) -> None:
    assert parse_slice_stem(text) == expected


@pytest.mark.parametrize(
    "text", [None, "", "slice.foo", "125-tasks.foo", "125-slice.", "125-slice..md"]
)
def test_other_shapes_give_none(text: str | None) -> None:
    assert parse_slice_stem(text) is None
