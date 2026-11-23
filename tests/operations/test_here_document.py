"""The gathered values and their document (slice 261, D5, D12)."""

from __future__ import annotations

import pytest

from amoeba.operations.errors import MALFORMED_CALL, NOT_SERVED, CallRefused
from amoeba.operations.here_document import (
    HereCaller,
    HereCheckout,
    HereNotAProject,
    here_to_document,
    parse_here,
)
from amoeba.wire.protocol import RefusalCode

CHECKOUT = HereCheckout(
    project_id="project_1_a",
    name="forge",
    path="/work/forge",
    origin="github.com/org/forge",
)


@pytest.mark.parametrize(
    ("value", "checkout"),
    [
        (HereCaller(project_id="project_1_a"), False),
        (CHECKOUT, True),
        (CHECKOUT.model_copy(update={"origin": None}), True),
        (HereNotAProject(not_a_project="not in a project"), False),
        (HereNotAProject(not_a_project="not in a project"), True),
    ],
)
def test_each_model_round_trips_through_its_document(
    value: HereCaller | HereCheckout | HereNotAProject, checkout: bool
) -> None:
    assert parse_here(here_to_document(value), checkout=checkout) == value


@pytest.mark.parametrize(
    ("value", "checkout", "field"),
    [
        (None, False, "here"),
        ("project_1_a", False, "here"),
        ([], True, "here"),
        ({}, False, "project_id"),
        ({"project_id": 5}, False, "project_id"),
        ({"project_id": "p", "extra": 1}, False, "extra"),
        ({"project_id": "p"}, True, "name"),
        ({"not_a_project": 5}, False, "not_a_project"),
    ],
)
def test_a_missing_wrong_kind_or_unknown_shape_is_refused_as_malformed(
    value: object, checkout: bool, field: str
) -> None:
    with pytest.raises(CallRefused) as refused:
        parse_here(value, checkout=checkout)

    assert refused.value.code == MALFORMED_CALL
    assert field in refused.value.message


@pytest.mark.parametrize(
    "origin",
    [
        "https://user:secret@github.com/org/forge.git",
        "GitHub.com/org/forge",
        "github.com/org/forge/",
        "git@github.com:org/forge",
    ],
)
def test_an_unreduced_origin_is_refused_without_naming_its_value(
    origin: str,
) -> None:
    document = {**here_to_document(CHECKOUT), "origin": origin}

    with pytest.raises(CallRefused) as refused:
        parse_here(document, checkout=True)

    assert refused.value.code == MALFORMED_CALL
    assert "origin" in refused.value.message
    assert "secret" not in refused.value.message
    assert origin not in refused.value.message


def test_the_two_refusal_codes_are_refusal_code_values() -> None:
    assert {MALFORMED_CALL, NOT_SERVED} <= {code.value for code in RefusalCode}
    assert RefusalCode(MALFORMED_CALL) is RefusalCode.MALFORMED_CALL
    assert RefusalCode(NOT_SERVED) is RefusalCode.NOT_SERVED
