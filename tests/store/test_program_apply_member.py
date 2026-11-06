"""register_member: upsert one member, remove nothing, reject three ways."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from program_harness import (
    install_stepping_clock,
    member,
    open_store,
    program_payload,
    register_member,
    register_program,
    table_snapshot,
    without_submissions,
)

from amoeba.store.inbox_models import SubmissionOutcome
from amoeba.store.program_models import ConsumptionMode, ProgramRejection
from amoeba.store.program_store import ProgramStore


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ProgramStore]:
    install_stepping_clock(monkeypatch)
    with open_store(tmp_path) as opened:
        register_program(opened)
        yield opened


def test_add_a_new_member(store: ProgramStore) -> None:
    program_before = store.program("demo")
    assert program_before is not None

    record = register_member(
        store, member("ui", initiative=791, consumed="from_release")
    )

    assert record.outcome is SubmissionOutcome.APPLIED
    assert [m.project_id for m in store.members("demo")] == ["data", "engine", "ui"]
    program_after = store.program("demo")
    assert program_after is not None
    assert program_after.updated_at > program_before.updated_at
    assert program_after.registered_at == program_before.registered_at
    assert store.program_of("ui") == program_after


def test_update_an_existing_member_replaces_its_override_set_only(
    store: ProgramStore,
) -> None:
    register_member(store, member("engine", overrides={"data": "from_release"}))
    data_0, engine_0 = store.members("demo")

    register_member(
        store,
        member(
            "engine",
            initiative=795,
            consumed="from_release",
            overrides={"data": "from_source"},
        ),
    )

    data_1, engine_1 = store.members("demo")
    assert data_1 == data_0
    assert engine_1.requests_initiative == 795
    assert engine_1.consumed is ConsumptionMode.FROM_RELEASE
    assert dict(engine_1.overrides) == {"data": ConsumptionMode.FROM_SOURCE}
    assert engine_1.updated_at > engine_0.updated_at
    assert engine_1.registered_at == engine_0.registered_at


def test_an_override_set_is_replaced_whole_not_merged(store: ProgramStore) -> None:
    register_member(store, member("engine", overrides={"data": "from_release"}))

    register_member(store, member("engine"))

    _, engine = store.members("demo")
    assert dict(engine.overrides) == {}


def test_an_identical_member_resubmission_changes_no_row(store: ProgramStore) -> None:
    register_member(store, member("ui"))
    before = without_submissions(table_snapshot(store))

    record = register_member(store, member("ui"))

    assert record.outcome is SubmissionOutcome.APPLIED
    assert without_submissions(table_snapshot(store)) == before


@pytest.mark.parametrize(
    ("program_id", "body", "code"),
    [
        ("nope", member("ui"), ProgramRejection.UNKNOWN_PROGRAM),
        ("demo2", member("data"), ProgramRejection.MEMBER_OF_OTHER_PROGRAM),
        (
            "demo",
            member("ui", overrides={"ghost": "from_release"}),
            ProgramRejection.OVERRIDE_NOT_MEMBER,
        ),
    ],
)
def test_each_rejection_is_recorded_and_writes_nothing_else(
    store: ProgramStore,
    program_id: str,
    body: dict[str, object],
    code: ProgramRejection,
) -> None:
    register_program(
        store,
        program_payload(program_id="demo2", concept_member="x", members=[member("x")]),
    )
    before = without_submissions(table_snapshot(store))

    record = register_member(store, body, program_id=program_id)

    assert record.outcome is SubmissionOutcome.REJECTED
    assert str(record.reason).startswith(f"{code.value}: ")
    assert without_submissions(table_snapshot(store)) == before


def test_an_override_may_name_the_member_being_added_by_a_peer(
    store: ProgramStore,
) -> None:
    """The override check is against the set after the write, so a peer counts."""
    record = register_member(store, member("ui", overrides={"engine": "from_release"}))

    assert record.outcome is SubmissionOutcome.APPLIED


def test_the_concept_member_is_still_a_member_afterwards(store: ProgramStore) -> None:
    register_member(store, member("ui"))
    register_member(store, member("data", initiative=792))

    program = store.program("demo")
    assert program is not None
    assert program.concept_member in {m.project_id for m in store.members("demo")}
