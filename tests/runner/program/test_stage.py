"""The program stage: its answers, its place in the tick, and its failure rules."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from program_harness import (
    member,
    program_payload,
    register_program,
)

import amoeba.runner.tick as tick_module
from amoeba.runner.faults import STORE_FAILURES
from amoeba.runner.program import ProgramStage
from amoeba.store import Program, ProgramStore, Store, StoreBusyError
from amoeba.store.paths import program_store_path
from runner.test_tenant import Rig as TenantRig
from runner.tick_support import PROJECT, Rig, drive_project, ready_slice

pytestmark = pytest.mark.usefixtures("passing_checks")

BUSY_TIMEOUT_SECONDS = 0.1


@pytest.fixture
def program_store(tmp_path: Path) -> Iterator[ProgramStore]:
    with ProgramStore.open(program_store_path(tmp_path / "supervisor")) as opened:
        yield opened


def _register(
    program_store: ProgramStore, *project_ids: str, program_id: str = "demo"
) -> None:
    register_program(
        program_store,
        program_payload(
            program_id=program_id,
            concept_member=project_ids[0],
            members=[member(project_id) for project_id in project_ids],
        ),
    )


# --------------------------------------------------------------------------
# What the stage answers
# --------------------------------------------------------------------------


def test_none_with_no_program_store() -> None:
    assert ProgramStage(None).run("a") is None


def test_none_for_a_project_in_no_program(program_store: ProgramStore) -> None:
    _register(program_store, "x", "y")

    assert ProgramStage(program_store).run("a") is None


def test_the_program_for_a_member(program_store: ProgramStore) -> None:
    _register(program_store, "a", "b")

    program = ProgramStage(program_store).run("b")

    assert isinstance(program, Program)
    assert (program.program_id, program.concept_member) == ("demo", "a")


# --------------------------------------------------------------------------
# Through the tenant: appearing at runtime, and the failure rules
# --------------------------------------------------------------------------


@pytest.fixture
def make_rig(tmp_path: Path) -> Iterator[type[TenantRig]]:
    rigs: list[TenantRig] = []

    class Tracked(TenantRig):
        def __init__(self, *project_ids: str) -> None:
            super().__init__(tmp_path, *project_ids)
            rigs.append(self)

    yield Tracked
    for rig in rigs:
        rig.close()


def _record_results(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    seen: list[tuple[str, Any]] = []
    original = ProgramStage.run

    def recording(self: ProgramStage, project_id: str) -> Program | None:
        result = original(self, project_id)
        seen.append((project_id, result))
        return result

    monkeypatch.setattr(ProgramStage, "run", recording)
    return seen


def test_a_store_that_appears_between_ticks_is_seen_on_the_second(
    make_rig: Any,
    program_store: ProgramStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig: TenantRig = make_rig("a")
    seen = _record_results(monkeypatch)

    rig.tenant.tick(rig.host)
    _register(program_store, "a", "b")
    rig.host.program_store = program_store
    rig.tenant.tick(rig.host)

    assert [project for project, _ in seen] == ["a", "a"]
    assert seen[0][1] is None
    assert isinstance(seen[1][1], Program)


@pytest.mark.parametrize("failure", ["closed", "busy"])
def test_a_program_store_failure_is_a_store_failure_and_leaves_no_fault_row(
    make_rig: Any,
    program_store: ProgramStore,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    rig: TenantRig = make_rig("a", "b")
    if failure == "closed":
        program_store.close()
    else:

        def locked(self: ProgramStore, project_id: str) -> Program | None:
            raise StoreBusyError("program store locked")

        monkeypatch.setattr(ProgramStore, "program_of", locked)
    rig.host.program_store = program_store

    with pytest.raises(STORE_FAILURES) as raised:
        rig.tenant.tick(rig.host)

    if failure == "busy":
        assert isinstance(raised.value, StoreBusyError)
    else:
        assert isinstance(raised.value, sqlite3.ProgrammingError)
    # A store failure stops the process; it is never a per-project fault.
    assert rig.stores["a"].open_project_escalations("a") == []
    assert rig.launches == 0


def test_a_non_store_exception_is_that_projects_fault_only(
    make_rig: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig: TenantRig = make_rig("a", "b")
    original = ProgramStage.run

    def exploding(self: ProgramStage, project_id: str) -> Program | None:
        if project_id == "a":
            raise RuntimeError("stage bug")
        return original(self, project_id)

    monkeypatch.setattr(ProgramStage, "run", exploding)

    rig.tenant.tick(rig.host)

    assert [m.fault_kind for m in rig.stores["a"].open_project_escalations("a")] == [
        "unexpected_fault"
    ]
    assert rig.launches == 1, "project b still ticked"


# --------------------------------------------------------------------------
# Its place in the tick, and that it changes nothing
# --------------------------------------------------------------------------


def test_the_stage_runs_after_resolutions_and_before_observe(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready_slice(store)
    drive_project(store)
    rig = Rig(tmp_path, store)
    events: list[str] = []

    real_resolutions = tick_module.apply_pending_resolutions
    real_observe = rig.observer.observe
    real_run = ProgramStage.run

    def resolutions(*args: Any, **kwargs: Any) -> bool:
        events.append("resolutions")
        return real_resolutions(*args, **kwargs)

    def observe(*args: Any, **kwargs: Any) -> Any:
        events.append("observe")
        return real_observe(*args, **kwargs)

    def stage(self: ProgramStage, project_id: str) -> Program | None:
        events.append("program-stage")
        return real_run(self, project_id)

    monkeypatch.setattr(tick_module, "apply_pending_resolutions", resolutions)
    monkeypatch.setattr(rig.observer, "observe", observe)
    monkeypatch.setattr(ProgramStage, "run", stage)

    rig.tick()

    assert events == ["resolutions", "program-stage", "observe"]


def _scripted_tick(tmp_path: Path, program_store: ProgramStore | None) -> object:
    """Tick one scripted project; everything observable except ids and times."""
    with Store.open(tmp_path / "project.sqlite3") as store:
        step = ready_slice(store)
        drive_project(store)
        rig = Rig(tmp_path, store)
        rig.program_store = program_store

        result, tick = rig.tick()

        return (
            result,
            tick.wrote,
            rig.popen.calls,
            [
                (entry.kind, entry.parameters["pipeline"], entry.parameters["params"])
                for entry in store.unresolved_journal_entries(PROJECT)
            ],
            [(node.title, node.status) for node in store.nodes_for_project(PROJECT)],
            store.open_project_escalations(PROJECT),
            step.title,
        )


def test_a_tick_is_identical_with_no_store_an_unrelated_program_or_its_own(
    tmp_path: Path,
) -> None:
    runs: dict[str, object] = {}
    for label in ("none", "unrelated", "own"):
        directory = tmp_path / label
        directory.mkdir()
        if label == "none":
            runs[label] = _scripted_tick(directory, None)
            continue
        with ProgramStore.open(program_store_path(directory)) as program_store:
            _register(
                program_store, *(("other",) if label == "unrelated" else (PROJECT,))
            )
            runs[label] = _scripted_tick(directory, program_store)

    assert runs["unrelated"] == runs["none"]
    assert runs["own"] == runs["none"]
