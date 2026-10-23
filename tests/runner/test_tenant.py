"""The Runner tenant: per-project fault isolation, carry-over and the return value."""

from __future__ import annotations

import ast
import logging
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

import amoeba.runner
from amoeba.process import ProcessSettings, RunOutcome, UpstreamShapeError
from amoeba.runner.decide import Action, LaunchRun, ProjectView
from amoeba.runner.launch import LAUNCH_LOGS_DIRNAME
from amoeba.runner.tenant import RunnerTenant
from amoeba.store import NodeKind, Store, StoreBusyError
from runner.observe_support import Child, Clock, FakeCf, ScriptedPoll, document

SETTINGS = ProcessSettings(tick_deadline_seconds=5.0, run_poll_interval_seconds=15.0)


class Host:
    def __init__(self, stores: dict[str, Store]) -> None:
        self.stores = stores
        self.stop_requested = False

    @property
    def project_ids(self) -> tuple[str, ...]:
        return tuple(self.stores)

    def store_for(self, project_id: str) -> Store:
        return self.stores[project_id]


class Planner:
    """Launches for every runnable node; may raise for one named project."""

    def __init__(self, checkout: Path) -> None:
        self.checkout = checkout
        self.seen: list[str] = []
        self.raise_for: dict[str, Exception] = {}

    def plan(self, view: ProjectView) -> Sequence[Action]:
        self.seen.append(view.project_id)
        if view.project_id in self.raise_for:
            raise self.raise_for[view.project_id]
        return [LaunchRun(n.id, "noop", {}, self.checkout) for n in view.runnable_nodes]


class Rig:
    def __init__(self, tmp_path: Path, *project_ids: str) -> None:
        supervisor_dir = tmp_path / "supervisor"
        (supervisor_dir / LAUNCH_LOGS_DIRNAME).mkdir(parents=True)
        self.stores = {p: Store.open(tmp_path / f"{p}.sqlite3") for p in project_ids}
        for project_id, store in self.stores.items():
            store.create_node(project_id=project_id, kind=NodeKind.SLICE, title="n")
        self.host = Host(self.stores)
        self.clock = Clock()
        self.planner = Planner(tmp_path)
        self.poll = ScriptedPoll()
        self.cf = FakeCf()
        self.launches = 0
        self.launch_cost = 0.0
        self.tenant = RunnerTenant(
            settings=SETTINGS,
            supervisor_dir=supervisor_dir,
            planners=(self.planner,),
            popen=self._popen,
            cf_run=self.cf,
            poll=self.poll,
            now=self.clock.wall,
            monotonic=self.clock.monotonic,
        )

    def _popen(self, argv: list[str], **kwargs: Any) -> Child:
        self.launches += 1
        self.clock.seconds += self.launch_cost
        return Child(None)

    def close(self) -> None:
        for store in self.stores.values():
            store.close()


@pytest.fixture
def make_rig(tmp_path: Path) -> Iterator[type[Rig]]:
    rigs: list[Rig] = []

    class Tracked(Rig):
        def __init__(self, *project_ids: str) -> None:
            super().__init__(tmp_path, *project_ids)
            rigs.append(self)

    yield Tracked
    for rig in rigs:
        rig.close()


def test_an_unexpected_exception_is_logged_and_the_other_project_still_ticks(
    make_rig: Any, caplog: pytest.LogCaptureFixture
) -> None:
    rig: Rig = make_rig("a", "b")
    rig.planner.raise_for["a"] = RuntimeError("planner exploded")

    with caplog.at_level(logging.ERROR):
        wrote = rig.tenant.tick(rig.host)

    assert wrote
    assert any(
        r.levelno == logging.ERROR and "project a" in r.getMessage()
        for r in caplog.records
    )
    assert [m.fault_kind for m in rig.stores["a"].open_project_escalations("a")] == [
        "unexpected_fault"
    ]
    assert rig.launches == 1, "project b launched in the same call"
    assert len(rig.stores["b"].unresolved_journal_entries("b")) == 1


@pytest.mark.parametrize(
    "error", [StoreBusyError("locked"), UpstreamShapeError("sq lacks --run-id")]
)
def test_a_store_failure_or_shape_error_propagates(
    make_rig: Any, error: Exception
) -> None:
    rig: Rig = make_rig("a", "b")
    rig.planner.raise_for["a"] = error

    with pytest.raises(type(error)):
        rig.tenant.tick(rig.host)

    assert rig.stores["a"].open_project_escalations("a") == []
    assert rig.launches == 0


def test_a_project_the_budget_did_not_reach_goes_first_next_tick(
    make_rig: Any,
) -> None:
    rig: Rig = make_rig("a", "b", "c")
    rig.launch_cost = 10.0  # one launch spends the whole tick deadline

    rig.tenant.tick(rig.host)
    assert rig.planner.seen == ["a"], "b and c were not reached"

    rig.planner.seen.clear()
    rig.tenant.tick(rig.host)
    assert rig.planner.seen[0] == "b"


def test_a_cut_off_project_is_ticked_first_next_time(make_rig: Any) -> None:
    rig: Rig = make_rig("a", "b")
    rig.launch_cost = 10.0
    second = rig.stores["a"].create_node(
        project_id="a", kind=NodeKind.SLICE, title="second"
    )

    rig.tenant.tick(rig.host)  # a launches one node, the budget is spent, a is cut off
    assert rig.launches == 1 and second.id

    rig.planner.seen.clear()
    rig.launch_cost = 0.0
    rig.tenant.tick(rig.host)
    assert rig.planner.seen[0] == "a"


def test_a_stop_request_runs_nothing_and_writes_nothing(make_rig: Any) -> None:
    rig: Rig = make_rig("a")
    rig.host.stop_requested = True

    assert rig.tenant.tick(rig.host) is False
    assert rig.launches == 0


def test_a_tick_that_only_polled_a_running_run_returns_false(make_rig: Any) -> None:
    rig: Rig = make_rig("a")
    assert rig.tenant.tick(rig.host) is True
    [entry] = rig.stores["a"].unresolved_journal_entries("a")
    rig.planner.raise_for.clear()
    rig.tenant._tracker.confirm(entry.id)  # pyright: ignore[reportPrivateUsage]
    rig.poll.answers.append(
        document(str(entry.parameters["run_id"]), RunOutcome.TIMED_OUT)
    )
    rig.clock.seconds = 20.0

    assert rig.tenant.tick(rig.host) is False
    assert len(rig.poll.asked) == 1


def test_the_runner_package_has_exactly_one_broad_except() -> None:
    package = Path(amoeba.runner.__file__).parent
    broad = [
        f"{path.name}:{node.lineno}"
        for path in sorted(package.glob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ExceptHandler)
        and (
            node.type is None
            or (
                isinstance(node.type, ast.Name)
                and node.type.id in {"Exception", "BaseException"}
            )
        )
    ]
    assert len(broad) == 1, broad
    assert broad[0].startswith("tenant.py")
