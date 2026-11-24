"""Two client machines in one test process, joined to one in-process hub (262 D16).

Each machine is its own ``AMOEBA_HOME``, joined with its own token; ``use`` points the
environment at one of them, so ``wiring.invoke`` and ``steps_for`` run as that machine.
Each machine has its own edges: a stub ``cf`` that knows its directories, a spawn
recorder, a scripted ``sq`` poll, and its own logs directory under its home with the
real file clean-up. The hub's
store can be seeded acting as either machine. A hook can drop a reply after commit
(``drop_next``), and the hub follows a clock the test moves.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from operations.pause_support import DepsRig, FakeChild, build_deps
from operations.status_support import FakeCf

from amoeba import wiring
from amoeba.config.home import HOME_VARIABLE, StateLayout, layout_under, state_layout
from amoeba.hub.calls import DoorHooks
from amoeba.operations.deps import Deps
from amoeba.operations.prune import prune
from amoeba.operations.prune_models import PruneReport
from amoeba.operations.steps.models_runs import OpenRunsReply
from amoeba.store.store import Store
from amoeba.upstream.squadron.run_list import ListedRun
from amoeba.upstream.squadron.run_outcome import RunPoll
from amoeba.wiring_door import join
from hub.call_support import ALPHA_TOKEN, BETA_TOKEN, NOW
from hub.in_process_hub import InProcessHub
from hub.join_support import line_for

ALPHA = "alpha"
BETA = "beta"
TOKENS = {ALPHA: ALPHA_TOKEN, BETA: BETA_TOKEN}


class ReplyDropped(Exception):
    """Raised after commit, so the client gets no reply (260 D18)."""


@dataclass
class Clock:
    """The one clock both the hub and the clients read."""

    now: datetime = NOW

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass
class Dropper:
    """Drops the reply of the next ``count`` committed calls."""

    count: int = 0

    def __call__(self) -> None:
        if self.count > 0:
            self.count -= 1
            raise ReplyDropped("the reply was lost after the commit")


@dataclass
class Machine:
    name: str
    home: Path
    directory: Path
    rig: DepsRig
    polls: dict[str, list[RunPoll]] = field(default_factory=lambda: {})

    @property
    def deps(self) -> Deps:
        return self.rig.deps

    @property
    def spawned(self) -> list[tuple[str, ...]]:
        return [call.argv for call in self.rig.spawner.calls]


@dataclass
class TwoHomes:
    hub: InProcessHub
    machines: dict[str, Machine]
    clock: Clock
    dropper: Dropper
    monkeypatch: pytest.MonkeyPatch

    def use(self, name: str) -> Machine:
        """Run what follows as machine ``name``."""
        machine = self.machines[name]
        self.monkeypatch.setenv(HOME_VARIABLE, str(machine.home))
        return machine

    @contextmanager
    def seeded(self, name: str) -> Generator[Store]:
        """The hub's store, acting as machine ``name``."""
        with self.hub.rig.open_store() as store:
            acting = self.hub.rig.machine(TOKENS[name])
            assert acting is not None
            store.act_as(acting)
            yield store

    def layout(self, name: str) -> StateLayout:
        self.use(name)
        return state_layout()


def _no_runs() -> list[ListedRun]:
    return []


def _machine(root: Path, name: str, clock: Clock, project_id: str) -> Machine:
    home = root / name
    directory = home / "checkout"
    directory.mkdir(parents=True)
    polls: dict[str, list[RunPoll]] = {}
    rig = build_deps(home, polls=polls, spawns=[FakeChild(exit_code=None)])
    layout = layout_under(home, home, None)

    def walk(open_runs: Callable[[], OpenRunsReply], *, now: datetime) -> PruneReport:
        return prune(open_runs, layout, now)

    deps = replace(
        rig.deps,
        cf_run=FakeCf({directory: project_id}),  # pyright: ignore[reportArgumentType]
        list_runs=_no_runs,
        clock=clock,
        amoeba_script=lambda: Path("/installed/bin/amoeba"),
        logs_dir=layout.logs_dir,
        prune=walk,
    )
    return Machine(name, home, directory, replace(rig, deps=deps), polls)


@contextmanager
def two_homes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    project_ids: Sequence[str],
) -> Generator[TwoHomes]:
    """A serving hub and ``alpha`` and ``beta`` joined to it; each machine's ``cf``
    answers its ``checkout`` directory as the project id given for it, in order."""
    clock = Clock()
    dropper = Dropper()
    with InProcessHub(tmp_path / "hub", DoorHooks(after_commit=dropper)) as hub:
        hub.rig.follows = clock
        machines: dict[str, Machine] = {}
        for name, project_id in zip((ALPHA, BETA), project_ids, strict=True):
            machine = _machine(tmp_path, name, clock, project_id)
            monkeypatch.setenv(HOME_VARIABLE, str(machine.home))
            join(line_for(hub, TOKENS[name]), set_aside_local=False)
            machines[name] = machine

        def deps_of(layout: StateLayout) -> Deps:
            return next(
                m.deps for m in machines.values() if layout.state_home == m.home
            )

        monkeypatch.setattr(wiring, "default_deps", deps_of)
        yield TwoHomes(hub, machines, clock, dropper, monkeypatch)
