"""``ChangesRequest``: ``since`` is required and must carry an offset."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from amoeba.operations.changes_models import ChangesRequest


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"since": "2026-11-09T12:00:00"},
        {"since": "not a time"},
        {"since": ""},
        {"since": "2026-11-09T12:00:00Z", "extra_field": "x"},
        {"since": None},
    ],
    ids=["missing", "no-offset", "unparseable", "empty", "unknown-field", "null"],
)
def test_an_invalid_document_is_rejected(document: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ChangesRequest.model_validate(document)


def test_a_valid_since_comes_back_as_utc_text() -> None:
    request = ChangesRequest.model_validate({"since": "2026-11-09T07:00:00-05:00"})
    assert request.since == "2026-11-09T12:00:00+00:00"
