"""The ``decisions`` request and the shared rejections (slice 224, 2.4)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from store.question_support import NOW
from store.seed import insert_program

from amoeba.operations.decisions import DecisionsRequest
from amoeba.operations.reject_codes import (
    RejectCode,
    unknown_program_problem,
    validation_problems,
)
from amoeba.store.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def test_a_request_with_no_fields_is_valid() -> None:
    request = DecisionsRequest.model_validate({})

    assert request.since is None
    assert request.program is None


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        ("2026-11-10T12:00:00+00:00", "2026-11-10T12:00:00+00:00"),
        ("2026-11-10T12:00:00Z", "2026-11-10T12:00:00+00:00"),
        ("2026-11-10T14:30:00+02:00", "2026-11-10T12:30:00+00:00"),
        ("2026-11-10T12:00:00.250000+00:00", "2026-11-10T12:00:00.250000+00:00"),
    ],
)
def test_a_valid_since_is_converted_to_the_stores_utc_text(
    given: str, stored: str
) -> None:
    assert DecisionsRequest.model_validate({"since": given}).since == stored


@pytest.mark.parametrize(
    "since", ["2026-11-10T12:00:00", "2026-11-10", "garbage", "", 1762000000]
)
def test_a_since_without_an_offset_or_unparsable_is_malformed(since: object) -> None:
    with pytest.raises(ValidationError) as caught:
        DecisionsRequest.model_validate({"since": since})

    assert "since" in validation_problems(caught.value)[0]


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError) as caught:
        DecisionsRequest.model_validate({"program": "a", "limit": 5})

    assert "limit" in validation_problems(caught.value)[0]


def test_a_blank_program_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DecisionsRequest.model_validate({"program": "  "})


def test_an_unknown_program_lists_the_known_ids(store: Store) -> None:
    with store.write() as transaction:
        for program in ("trading", "tools"):
            insert_program(
                transaction,
                program_id=program,
                concept_member=None,
                concept_path=None,
                registered_at=NOW,
                updated_at=NOW,
            )

    with store.read() as transaction:
        problem = unknown_program_problem(transaction, "nope")
        known = unknown_program_problem(transaction, "tools")

    assert problem is not None
    assert "nope" in problem
    assert "tools, trading" in problem
    assert known is None


def test_an_unknown_program_with_none_registered_says_so(store: Store) -> None:
    with store.read() as transaction:
        problem = unknown_program_problem(transaction, "nope")

    assert problem is not None
    assert "none registered" in problem


def test_the_rejection_codes_are_the_closed_set() -> None:
    assert {code.value for code in RejectCode} == {
        "unknown_program",
        "malformed",
        "beyond_last_record",
        "not_a_member",
        "not_reported",
    }
