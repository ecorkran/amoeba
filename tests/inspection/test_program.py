"""The program listings: ``program``, ``program-submissions``, ``program-blocked``."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from program_harness import (
    CF_PROJECT_ID,
    link_member_store,
    member,
    observe,
    open_member_store,
    program_payload,
    register_member,
    register_program,
)

from amoeba.inspection import ListingRequest, read_listing
from amoeba.inspection import core as inspection_core
from amoeba.store import BlockedKind, NodeKind, ProgramStore, Store, StoreBusyError, sql
from amoeba.store.migrations import EXPECTED_PROGRAM_SCHEMA_VERSION
from amoeba.store.models import StoreSchemaError
from amoeba.store.paths import program_store_path, project_store_path

REQUEST = ListingRequest(project_id=None, options={}, compact=False)


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def checkout_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "checkout"
    directory.mkdir()
    return directory


def _rows(name: str, supervisor_dir: Path) -> list[dict[str, object]]:
    return read_listing(name, REQUEST, supervisor_dir).rows


def _register(supervisor_dir: Path, *members: dict[str, object], concept: str) -> None:
    with ProgramStore.open(program_store_path(supervisor_dir)) as store:
        register_program(
            store,
            program_payload(concept_member=concept, members=list(members)),
        )


def _ready_member(supervisor_dir: Path, project: str, checkout: Path) -> None:
    with open_member_store(supervisor_dir, project) as store:
        link_member_store(store, project, CF_PROJECT_ID)
        observe(store, project, CF_PROJECT_ID, project_path=checkout)


def _block_a_node(supervisor_dir: Path, project: str, title: str = "gate") -> str:
    with Store.open(project_store_path(supervisor_dir, project)) as store:
        node = store.create_node(project_id=project, kind=NodeKind.GATE, title=title)
        store.block(node.id, kind=BlockedKind.HUMAN, context="needs a decision")
        return node.id


def _five_unreadable_members(
    supervisor_dir: Path, checkout: Path, tmp_path: Path
) -> None:
    """One member per unreadable reason, plus one readable."""
    _ready_member(supervisor_dir, "ready", checkout)
    # store_missing: no file for "missing".
    project_store_path(supervisor_dir, "corrupt").write_bytes(b"junk" * 100)
    open_member_store(supervisor_dir, "unlinked").close()
    with open_member_store(supervisor_dir, "nosnap") as store:
        link_member_store(store, "nosnap", CF_PROJECT_ID)
    with open_member_store(supervisor_dir, "nocheckout") as store:
        link_member_store(store, "nocheckout", CF_PROJECT_ID)
        observe(store, "nocheckout", CF_PROJECT_ID, project_path=tmp_path / "gone")
    _register(
        supervisor_dir,
        *(
            member(name)
            for name in (
                "ready",
                "missing",
                "corrupt",
                "unlinked",
                "nosnap",
                "nocheckout",
            )
        ),
        concept="ready",
    )


# --------------------------------------------------------------------------
# program
# --------------------------------------------------------------------------


def test_no_program_store_gives_no_rows_in_every_listing(supervisor_dir: Path) -> None:
    for name in ("program", "program-blocked", "program-submissions"):
        assert _rows(name, supervisor_dir) == []
    assert not program_store_path(supervisor_dir).exists()


def test_program_lists_each_member_with_its_state_and_overrides(
    supervisor_dir: Path, checkout_dir: Path
) -> None:
    _ready_member(supervisor_dir, "data", checkout_dir)
    _register(
        supervisor_dir,
        member("data", initiative=790),
        member(
            "engine",
            initiative=791,
            consumed="from_release",
            overrides={"data": "from_release"},
        ),
        concept="data",
    )

    data, engine = _rows("program", supervisor_dir)

    assert data["program_id"] == "demo"
    assert (data["project_id"], data["requests_initiative"]) == ("data", 790)
    assert (data["state"], data["detail"]) == ("readable", "")
    assert data["concept_path"] == "docs/concept.md"
    assert data["overrides"] == ""
    assert engine["consumed"] == "from_release"
    assert engine["overrides"] == "data=from_release"
    assert engine["concept_path"] == ""
    assert engine["state"] == "store_missing"
    assert "engine.sqlite3" in str(engine["detail"])


def test_program_names_every_unreadable_reason(
    supervisor_dir: Path, checkout_dir: Path, tmp_path: Path
) -> None:
    _five_unreadable_members(supervisor_dir, checkout_dir, tmp_path)

    states = {
        row["project_id"]: row["state"] for row in _rows("program", supervisor_dir)
    }

    assert states == {
        "ready": "readable",
        "missing": "store_missing",
        "corrupt": "store_unreadable",
        "unlinked": "unlinked",
        "nosnap": "snapshot_missing",
        "nocheckout": "checkout_unresolved",
    }


def test_a_wrong_version_program_store_raises(supervisor_dir: Path) -> None:
    _register(supervisor_dir, member("data"), concept="data")
    with sqlite3.connect(program_store_path(supervisor_dir)) as connection:
        connection.execute(
            sql.UPSERT_SCHEMA_VERSION,
            (sql.SCHEMA_META_ROW_ID, EXPECTED_PROGRAM_SCHEMA_VERSION + 1),
        )

    for name in ("program", "program-blocked", "program-submissions"):
        with pytest.raises(StoreSchemaError):
            _rows(name, supervisor_dir)


# --------------------------------------------------------------------------
# program-submissions
# --------------------------------------------------------------------------


def test_program_submissions_lists_applied_and_rejected_in_order(
    supervisor_dir: Path,
) -> None:
    with ProgramStore.open(program_store_path(supervisor_dir)) as store:
        register_program(store, submission_id="first")
        register_member(store, member("ui"), program_id="nope", submission_id="second")

    first, second = _rows("program-submissions", supervisor_dir)

    assert (first["id"], first["kind"], first["outcome"]) == (
        "first",
        "register_program",
        "applied",
    )
    assert first["reason"] == ""
    assert (second["id"], second["outcome"]) == ("second", "rejected")
    assert str(second["reason"]).startswith("unknown_program: ")
    assert first["submitted_by"] == "tester"


# --------------------------------------------------------------------------
# program-blocked
# --------------------------------------------------------------------------


def test_members_blocked_nodes_carry_the_program_id(
    supervisor_dir: Path, checkout_dir: Path
) -> None:
    _ready_member(supervisor_dir, "data", checkout_dir)
    _ready_member(supervisor_dir, "engine", checkout_dir)
    data_node = _block_a_node(supervisor_dir, "data", "data gate")
    engine_node = _block_a_node(supervisor_dir, "engine", "engine gate")
    _register(supervisor_dir, member("data"), member("engine"), concept="data")

    rows = _rows("program-blocked", supervisor_dir)

    assert {(r["program_id"], r["project_id"], r["node_id"]) for r in rows} == {
        ("demo", "data", data_node),
        ("demo", "engine", engine_node),
    }
    assert {r["blocked_on"] for r in rows} == {"human"}
    assert list(rows[0])[:3] == ["program_id", "project_id", "node_id"]


def test_each_unreadable_reason_yields_its_row(
    supervisor_dir: Path, checkout_dir: Path, tmp_path: Path
) -> None:
    _five_unreadable_members(supervisor_dir, checkout_dir, tmp_path)

    rows = _rows("program-blocked", supervisor_dir)

    reasons = {r["project_id"]: str(r["reason"]).split(":")[0] for r in rows}
    assert reasons == {
        "missing": "store_missing",
        "corrupt": "store_unreadable",
        "unlinked": "unlinked",
        "nosnap": "snapshot_missing",
        "nocheckout": "checkout_unresolved",
    }
    assert {r["blocked_on"] for r in rows} == {"member_unreadable"}
    assert all(r["node_id"] == "" and r["title"] == "" for r in rows)


def test_a_member_whose_store_opens_but_is_unlinked_appears_both_ways(
    supervisor_dir: Path,
) -> None:
    node_id = _block_a_node(supervisor_dir, "data")
    _register(supervisor_dir, member("data"), concept="data")

    node_row, unreadable_row = _rows("program-blocked", supervisor_dir)

    assert node_row["node_id"] == node_id and node_row["blocked_on"] == "human"
    assert unreadable_row["blocked_on"] == "member_unreadable"
    assert str(unreadable_row["reason"]).startswith("unlinked: ")


def test_a_corrupt_member_store_does_not_stop_the_other_members(
    supervisor_dir: Path, checkout_dir: Path
) -> None:
    _ready_member(supervisor_dir, "good", checkout_dir)
    good_node = _block_a_node(supervisor_dir, "good")
    project_store_path(supervisor_dir, "bad").write_bytes(b"junk" * 100)
    _register(supervisor_dir, member("bad"), member("good"), concept="good")

    rows = _rows("program-blocked", supervisor_dir)

    assert {r["node_id"] for r in rows if r["blocked_on"] == "human"} == {good_node}
    [bad_row] = [r for r in rows if r["project_id"] == "bad"]
    assert str(bad_row["reason"]).startswith("store_unreadable: ")


def test_a_blocked_read_failure_on_an_opened_store_is_that_members_row(
    supervisor_dir: Path, checkout_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for project in ("bad", "good"):
        _ready_member(supervisor_dir, project, checkout_dir)
    good_node = _block_a_node(supervisor_dir, "good")
    _register(supervisor_dir, member("bad"), member("good"), concept="good")
    real = inspection_core.project_blocked_rows

    def failing(store: Store, project_id: str) -> list[dict[str, object]]:
        if project_id == "bad":
            raise StoreBusyError("injected: member store is busy")
        return real(store, project_id)

    monkeypatch.setattr(inspection_core, "project_blocked_rows", failing)

    rows = _rows("program-blocked", supervisor_dir)

    [bad_row] = [r for r in rows if r["project_id"] == "bad"]
    assert bad_row["blocked_on"] == "member_unreadable"
    assert str(bad_row["reason"]) == "store_unreadable: injected: member store is busy"
    assert bad_row["node_id"] == ""
    assert {r["node_id"] for r in rows if r["project_id"] == "good"} == {good_node}


def test_inspection_works_with_the_process_stopped_and_writes_nothing(
    supervisor_dir: Path, checkout_dir: Path
) -> None:
    _ready_member(supervisor_dir, "data", checkout_dir)
    _block_a_node(supervisor_dir, "data")
    _register(supervisor_dir, member("data"), concept="data")
    watched = [
        program_store_path(supervisor_dir),
        project_store_path(supervisor_dir, "data"),
    ]
    before = [path.read_bytes() for path in watched]

    for name in ("program", "program-blocked", "program-submissions"):
        _rows(name, supervisor_dir)

    assert [path.read_bytes() for path in watched] == before
