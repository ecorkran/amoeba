"""The nodes listing shows a node's Context Forge index, in both forms."""

from __future__ import annotations

import json

import pytest

from amoeba.cli.inspect import _print_table  # pyright: ignore[reportPrivateUsage]
from amoeba.inspection import LISTINGS_BY_NAME
from amoeba.inspection.core import node_rows
from amoeba.inspection.listing import ListingRequest, Row
from amoeba.store import Store
from amoeba.store.models import CFReference, NodeKind

PROJECT = "demo"
LINKED_INDEX = 123

#: The columns the listing had before the index was added.
_EXISTING_COLUMNS = ("id", "kind", "status", "title", "parent_id")


def _rows() -> list[Row]:
    with Store.open_temporary() as store:
        store.create_node(
            project_id=PROJECT,
            kind=NodeKind.SLICE,
            title="linked",
            cf=CFReference(project="cf-a", index=LINKED_INDEX),
        )
        store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="unlinked")
        request = ListingRequest(project_id=PROJECT, options={}, compact=False)
        return node_rows(store, request)


def test_the_listing_declares_the_index_column_after_the_existing_ones() -> None:
    columns = LISTINGS_BY_NAME["nodes"].columns
    assert columns == (*_EXISTING_COLUMNS, "cf_index")


def test_a_node_with_an_index_shows_it_and_one_without_is_null() -> None:
    by_title = {row["title"]: row for row in _rows()}
    assert by_title["linked"]["cf_index"] == LINKED_INDEX
    assert by_title["unlinked"]["cf_index"] is None


def test_the_json_form_carries_a_number_and_a_null() -> None:
    decoded = json.loads(json.dumps(_rows(), default=str))
    assert {row["title"]: row["cf_index"] for row in decoded} == {
        "linked": LINKED_INDEX,
        "unlinked": None,
    }


def test_existing_columns_are_unchanged() -> None:
    for row in _rows():
        assert tuple(row)[: len(_EXISTING_COLUMNS)] == _EXISTING_COLUMNS


def test_the_table_shows_the_index_and_an_empty_cell_without_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _print_table(LISTINGS_BY_NAME["nodes"].columns, _rows())
    lines = capsys.readouterr().out.splitlines()

    header, *body = lines[0], *lines[2:]
    index_start = header.index("cf_index")
    cells = {line.split()[3]: line[index_start:].strip() for line in body}
    assert cells == {"linked": str(LINKED_INDEX), "unlinked": ""}
