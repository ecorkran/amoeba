"""A whole ``handle_pause`` world for tests (slice 223, section 7).

Real: the store, the asking checkout (a git repo) and ``git``. Replayed: ``cf`` (plan
reads, project, target) and ``sq runs wait`` (the paused run's polls are scripted from
the recordings; an answering run polls as completed unless a test says otherwise).
Played: ``sq run`` is a spawner that, for an answering run, writes the answer and
check replies into its scratch directory, as the pipeline would, and for a resume
returns a child that stays alive.
"""

from __future__ import annotations

import atexit
import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, cast

from answering.sources_repo import build_sources_repo
from cf_fixtures import DEFAULT_WORKTREE, fixture_document
from cf_plan_run import PlanCfRun, plan_cf_run
from fake_sq import (
    COMPLETED,
    PAUSED_AGENT_QUESTION,
    RUN_FILE,
    RUNNING,
    SQUADRON_FIXTURES,
    poll_result,
)
from user_configs import user_config

from amoeba.answering.settings import AnswererSettings
from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.handle_pause import HandlePauseResult, handle_pause
from amoeba.operations.member_answering import answering_for
from amoeba.operations.processes import WaitableChild
from amoeba.store.models import Member, QuestionKey
from amoeba.store.store import Store
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs
from amoeba.upstream.squadron.run_outcome import RunPoll
from operations.pause_support import FakeChild, build_deps, register_member

RUN = "demo-run"
PROJECT_ID: str = fixture_document(DEFAULT_WORKTREE)["id"]
PAUSE = poll_result(PAUSED_AGENT_QUESTION, RUN)
assert PAUSE.checkpoint is not None
PAUSED_AT = PAUSE.checkpoint.paused_at_text or ""
QUESTION = PAUSE.checkpoint.question or ""
KEY = QuestionKey(RUN, PAUSED_AT)
RUNNING_DOC = poll_result(RUNNING, RUN)
OTHER_PAUSE = poll_result("resume_lock_before.json", RUN)

ANSWER_TEXT = "Source files stay near 300 lines."
PROPOSED: dict[str, object] = {"kind": "answer", "answer": ANSWER_TEXT, "cited": ["P1"]}
CHECK_YES: dict[str, object] = {"verdict": "yes", "reason": "CLAUDE.md says so"}
CHECK_NO: dict[str, object] = {"verdict": "no", "reason": "not settled"}
#: What the paused run's polls say through a happy path: eligibility, the resume's
#: first look, then the run running.
HAPPY_PAUSED_POLLS: tuple[RunPoll, ...] = (PAUSE, PAUSE, RUNNING_DOC)


@dataclass
class SpawnLog:
    """Every child the world started, in order."""

    argvs: list[tuple[str, ...]] = field(default_factory=lambda: [])
    cwds: list[Path] = field(default_factory=lambda: [])

    @property
    def answering(self) -> list[tuple[str, ...]]:
        return [a for a in self.argvs if "--resume" not in a]

    @property
    def resumes(self) -> list[tuple[str, ...]]:
        return [a for a in self.argvs if "--resume" in a]


@dataclass
class World:
    """The world, and the handles a test pulls on."""

    store: Store
    config: UserConfig
    deps: Deps
    directory: Path
    member: Member
    spawned: SpawnLog
    cf: PlanCfRun
    runs_dir: Path
    answering_poll: Callable[[str], RunPoll]

    def member_settings(self) -> AnswererSettings:
        """The answering settings ``handle_pause`` derives for this world's member."""
        return answering_for(self.member.settings, self.config).settings

    def handle(self) -> HandlePauseResult:
        return handle_pause(
            self.store, self.config, RUN, directory=self.directory, deps=self.deps
        )


_TEMPLATE: list[Path] = []


def _fresh_checkout(destination: Path) -> Path:
    """A copy of one asking checkout, built once per test session: the real
    committed history of the sources fixtures, without a rebuild for every test."""
    if not _TEMPLATE:
        root = Path(tempfile.mkdtemp(prefix="amoeba-handle-rig-"))
        atexit.register(shutil.rmtree, root, ignore_errors=True)
        _TEMPLATE.append(build_sources_repo(root / "template").path)
    shutil.copytree(_TEMPLATE[0], destination)
    return destination


def _completed_for(run_id: str) -> RunPoll:
    return poll_result(COMPLETED, run_id)


def _run_file(runs_dir: Path, params: dict[str, str]) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    document = json.loads((SQUADRON_FIXTURES / RUN_FILE).read_text(encoding="utf-8"))
    document["params"] = params
    (runs_dir / f"{RUN}.json").write_text(json.dumps(document), encoding="utf-8")


@contextmanager
def world(  # noqa: PLR0913 - the knobs a handle_pause test turns
    tmp_path: Path,
    *,
    paused_polls: Sequence[RunPoll] = HAPPY_PAUSED_POLLS,
    answer: dict[str, object] | None = PROPOSED,
    check: dict[str, object] | None = CHECK_YES,
    params: dict[str, str] | None = None,
    answering_poll: Callable[[str], RunPoll] = _completed_for,
    config: UserConfig | None = None,
    on_poll: Callable[[str], None] | None = None,
) -> Generator[World]:
    """A store with one member and a checkout, ready for ``handle_pause``."""
    directory = _fresh_checkout(tmp_path / "checkout")
    runs_dir = tmp_path / "runs"
    _run_file(runs_dir, {"model": "haiku-xhigh"} if params is None else params)
    spawned = SpawnLog()
    paused = list(paused_polls)
    asked = {"count": 0}

    def poll(run_id: str) -> RunPoll:
        if on_poll is not None:
            on_poll(run_id)
        if run_id != RUN:
            return worldview.answering_poll(run_id)
        position = min(asked["count"], len(paused) - 1)
        asked["count"] += 1
        return paused[position]

    def spawner(
        argv: Sequence[str], cwd: Path, logs: LaunchLogs
    ) -> WaitableChild | LaunchError:
        spawned.argvs.append(tuple(argv))
        spawned.cwds.append(cwd)
        if "--resume" in argv:
            return FakeChild(exit_code=None)
        for name, reply in (("answer.json", answer), ("check.json", check)):
            if reply is not None:
                (cwd / name).write_text(json.dumps(reply), encoding="utf-8")
        return FakeChild(exit_code=0)

    cf = plan_cf_run(integration_branch="", broken=False)
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        member = register_member(store, PROJECT_ID)
        rig = build_deps(tmp_path, polls={}, spawns=[], spawner=spawner)
        deps = replace(
            rig.deps, poll_run=poll, cf_run=_as_run(cf), squadron_runs_dir=runs_dir
        )
        worldview = World(
            store=store,
            config=config or user_config(),
            deps=deps,
            directory=directory,
            member=member,
            spawned=spawned,
            cf=cf,
            runs_dir=runs_dir,
            answering_poll=answering_poll,
        )
        yield worldview


def _as_run(cf: PlanCfRun) -> Callable[..., subprocess.CompletedProcess[str]]:
    """``git`` runs for real; every ``cf`` call is replayed."""

    def run(argv: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if argv[0] == "cf":
            return cf(argv)
        return cast(
            "subprocess.CompletedProcess[str]",
            subprocess.run(list(argv), **kwargs),  # noqa: PLW1510
        )

    return run
