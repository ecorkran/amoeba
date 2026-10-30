"""Tests for the listing registry's types: flag derivation, scope, the request."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.inspection.listing import (
    ChoiceOption,
    FlagOption,
    Listing,
    ListingOption,
    ListingRequest,
    ListingScope,
    Row,
    ValueOption,
)
from amoeba.store import Store

_FLAG = FlagOption(name="only_open", help_text="h")
_CHOICE = ChoiceOption(name="only_open", help_text="h", choices=("a", "b"))
_VALUE = ValueOption(name="judge_invocation_id", help_text="h", metavar="ID")


def _project_rows(store: Store, request: ListingRequest) -> list[Row]:
    return []


def _supervisor_rows(supervisor_dir: Path) -> list[Row]:
    return []


def test_value_option_flag_derives_from_name() -> None:
    assert _VALUE.flag == "--judge-invocation-id"


@pytest.mark.parametrize("option", [_FLAG, _CHOICE])
def test_every_option_class_derives_its_flag_the_same_way(
    option: ListingOption,
) -> None:
    assert option.flag == "--only-open"


def test_a_listing_with_neither_row_function_is_refused() -> None:
    with pytest.raises(ValueError, match="rows, supervisor_rows or both"):
        Listing(name="x", help_text="h", columns=())


def test_scope_follows_the_row_function() -> None:
    project = Listing(name="p", help_text="h", columns=(), rows=_project_rows)
    supervisor = Listing(
        name="s", help_text="h", columns=(), supervisor_rows=_supervisor_rows
    )

    assert project.scope is ListingScope.PROJECT
    assert supervisor.scope is ListingScope.SUPERVISOR


def test_both_row_functions_make_the_project_optional() -> None:
    both = Listing(
        name="b",
        help_text="h",
        columns=(),
        rows=_project_rows,
        supervisor_rows=_supervisor_rows,
    )
    project = Listing(name="p", help_text="h", columns=(), rows=_project_rows)

    assert both.scope is ListingScope.PROJECT
    assert both.project_optional
    assert not project.project_optional


def test_option_returns_the_stored_value() -> None:
    request = ListingRequest(
        project_id="demo",
        options={"only_open": True, "judge_invocation_id": "j1"},
        compact=False,
    )

    assert request.option(_FLAG) is True
    assert request.option(_VALUE) == "j1"


def test_option_returns_none_when_supplied_as_none() -> None:
    request = ListingRequest(
        project_id="demo", options={"judge_invocation_id": None}, compact=False
    )

    assert request.option(_VALUE) is None


def test_option_absent_from_the_request_raises_key_error() -> None:
    request = ListingRequest(project_id="demo", options={}, compact=False)

    with pytest.raises(KeyError, match="judge_invocation_id"):
        request.option(_VALUE)


def test_option_with_a_value_of_the_wrong_type_raises() -> None:
    request = ListingRequest(
        project_id="demo", options={"only_open": "yes"}, compact=False
    )

    with pytest.raises(TypeError, match="only_open"):
        request.option(_FLAG)


def test_require_project_id_returns_the_project() -> None:
    request = ListingRequest(project_id="demo", options={}, compact=False)

    assert request.require_project_id() == "demo"


def test_require_project_id_without_a_project_raises() -> None:
    request = ListingRequest(project_id=None, options={}, compact=False)

    with pytest.raises(ValueError, match="project id"):
        request.require_project_id()
