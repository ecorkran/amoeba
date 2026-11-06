"""register_program rejections: recorded, nothing else written, in a fixed order."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from program_harness import (
    member,
    open_store,
    program_payload,
    register_program,
    table_snapshot,
    without_submissions,
)

from amoeba.store.inbox_models import SubmissionOutcome
from amoeba.store.program_models import ProgramRejection
from amoeba.store.program_store import ProgramStore


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ProgramStore]:
    with open_store(tmp_path) as opened:
        register_program(opened, program_payload(program_id="first"))
        yield opened


def _code(reason: str | None) -> str:
    assert reason is not None
    return reason.split(":", 1)[0]


def _rejected_bodies() -> list[tuple[dict[str, object], ProgramRejection]]:
    return [
        (
            program_payload(
                program_id="second", members=[member("data"), member("ui")]
            ),
            ProgramRejection.MEMBER_OF_OTHER_PROGRAM,
        ),
        (
            program_payload(
                program_id="second",
                concept_member="ghost",
                members=[member("ui"), member("api")],
            ),
            ProgramRejection.CONCEPT_MEMBER_NOT_MEMBER,
        ),
        (
            program_payload(
                program_id="second",
                concept_member="ui",
                members=[member("ui", overrides={"ghost": "from_release"})],
            ),
            ProgramRejection.OVERRIDE_NOT_MEMBER,
        ),
    ]


@pytest.mark.parametrize(("body", "code"), _rejected_bodies())
def test_each_rejection_is_recorded_and_writes_nothing_else(
    store: ProgramStore, body: dict[str, object], code: ProgramRejection
) -> None:
    before = without_submissions(table_snapshot(store))
    seq_before = store.submissions()[-1].applied_seq

    record = register_program(store, body)

    assert record.outcome is SubmissionOutcome.REJECTED
    assert _code(record.reason) == code.value
    assert str(record.reason).startswith(f"{code.value}: ")
    assert record.applied_seq == seq_before + 1
    assert without_submissions(table_snapshot(store)) == before
    assert store.submission(record.id) == record


def test_with_two_problems_the_first_in_order_is_recorded(store: ProgramStore) -> None:
    """Another program's member, a missing concept member and a bad override."""
    body = program_payload(
        program_id="second",
        concept_member="ghost",
        members=[member("data", overrides={"phantom": "from_release"})],
    )

    record = register_program(store, body)

    assert _code(record.reason) == ProgramRejection.MEMBER_OF_OTHER_PROGRAM.value


def test_concept_member_is_checked_before_overrides(store: ProgramStore) -> None:
    body = program_payload(
        program_id="second",
        concept_member="ghost",
        members=[member("ui", overrides={"phantom": "from_release"})],
    )

    record = register_program(store, body)

    assert _code(record.reason) == ProgramRejection.CONCEPT_MEMBER_NOT_MEMBER.value


def test_replacing_a_program_does_not_trip_member_of_other_program(
    store: ProgramStore,
) -> None:
    """A project already in *this* program is not 'another program's' member."""
    record = register_program(store, program_payload(program_id="first"))

    assert record.outcome is SubmissionOutcome.APPLIED
