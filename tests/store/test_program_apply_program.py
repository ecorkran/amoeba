"""register_program writes: create, replace whole, idempotence, timestamps."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from program_harness import (
    install_stepping_clock,
    member,
    open_store,
    program_payload,
    register_program,
    table_snapshot,
    without_submissions,
)

from amoeba.store._program_writer import ProgramWriter
from amoeba.store.inbox_models import SubmissionOutcome
from amoeba.store.program_models import ConsumptionMode
from amoeba.store.program_store import ProgramStore


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ProgramStore]:
    install_stepping_clock(monkeypatch)
    with open_store(tmp_path) as opened:
        yield opened


def test_create_writes_the_program_members_and_overrides(store: ProgramStore) -> None:
    record = register_program(
        store,
        program_payload(
            members=[
                member("data"),
                member(
                    "engine",
                    consumed="from_release",
                    overrides={"data": "from_release"},
                ),
            ]
        ),
    )

    assert record.outcome is SubmissionOutcome.APPLIED
    assert record.applied_seq == 1
    assert record.reason is None
    program = store.program("demo")
    assert program is not None
    assert (program.concept_member, program.concept_path) == ("data", "docs/concept.md")
    data, engine = store.members("demo")
    assert (data.project_id, engine.project_id) == ("data", "engine")
    assert engine.consumed is ConsumptionMode.FROM_RELEASE
    assert dict(engine.overrides) == {"data": ConsumptionMode.FROM_RELEASE}
    assert store.program_of("engine") == program


def test_replace_with_a_member_left_out_removes_it_and_its_overrides(
    store: ProgramStore,
) -> None:
    register_program(
        store,
        program_payload(
            members=[
                member("data"),
                member("engine", overrides={"data": "from_release"}),
            ]
        ),
    )

    record = register_program(
        store, program_payload(members=[member("data"), member("ui")])
    )

    assert record.outcome is SubmissionOutcome.APPLIED
    assert [m.project_id for m in store.members("demo")] == ["data", "ui"]
    assert store.program_of("engine") is None
    overrides = table_snapshot(store)["consumption_overrides"]
    assert overrides == []


def test_replace_changes_the_concept_location(store: ProgramStore) -> None:
    register_program(store)
    register_program(
        store, program_payload(concept_member="engine", concept_path="docs/other.md")
    )

    program = store.program("demo")
    assert program is not None
    assert (program.concept_member, program.concept_path) == ("engine", "docs/other.md")


def test_an_identical_resubmission_is_applied_and_changes_no_row(
    store: ProgramStore,
) -> None:
    register_program(store)
    before = without_submissions(table_snapshot(store))

    record = register_program(store)

    assert record.outcome is SubmissionOutcome.APPLIED
    assert without_submissions(table_snapshot(store)) == before
    assert len(store.submissions()) == 2


def test_timestamps_follow_the_documented_rules(store: ProgramStore) -> None:
    register_program(store)
    program_0 = store.program("demo")
    data_0, engine_0 = store.members("demo")
    assert program_0 is not None

    # A changed mode advances that member and the program only.
    register_program(
        store,
        program_payload(
            members=[member("data"), member("engine", consumed="from_release")]
        ),
    )
    program_1 = store.program("demo")
    data_1, engine_1 = store.members("demo")
    assert program_1 is not None
    assert program_1.updated_at > program_0.updated_at
    assert engine_1.updated_at > engine_0.updated_at
    assert data_1.updated_at == data_0.updated_at

    # A removed member advances the program only.
    register_program(store, program_payload(members=[member("data")]))
    program_2 = store.program("demo")
    (data_2,) = store.members("demo")
    assert program_2 is not None
    assert program_2.updated_at > program_1.updated_at
    assert data_2.updated_at == data_0.updated_at

    # registered_at never moves.
    assert program_2.registered_at == program_0.registered_at
    assert data_2.registered_at == data_0.registered_at


def test_first_wins_a_reused_id_is_a_no_op_even_with_different_content(
    store: ProgramStore,
) -> None:
    first = register_program(store, submission_id="same")
    before = table_snapshot(store)

    second = register_program(
        store, program_payload(program_id="other"), submission_id="same"
    )

    assert second == first
    assert table_snapshot(store) == before
    assert len(store.submissions()) == 1


def test_a_failure_inside_the_transaction_leaves_no_submission_row(
    store: ProgramStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _explode(*args: object, **kwargs: object) -> bool:
        raise RuntimeError("provoked failure after the program row was written")

    monkeypatch.setattr(ProgramWriter, "_write_member", _explode)

    with pytest.raises(RuntimeError, match="provoked"):
        register_program(store)

    snapshot = table_snapshot(store)
    snapshot.pop("schema_meta")
    assert all(rows == [] for rows in snapshot.values())
    assert store.submissions() == []
    assert store.programs() == []
