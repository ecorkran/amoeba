"""``handle_pause`` (after any resume) and ``status`` call ``prune`` (228 D9)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from store.decision_support import CORE, LINT, seed_programs
from store.question_support import claimed_question
from user_configs import user_config

from amoeba.config.home import StateLayout
from amoeba.operations.dismiss import dismiss
from amoeba.operations.handle_pause import handle_pause
from amoeba.operations.pause_models import HandlePauseOutcome
from amoeba.operations.prune import prune
from amoeba.operations.prune_models import Prune, PruneReport
from amoeba.operations.status import StatusResult, status
from amoeba.store.errors import StoreBusyError
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from operations.handle_rig import RUN, world
from operations.status_support import FakeCf, status_deps

NAMES = {CORE: "core-name", LINT: "lint-name"}
OLD_DAYS = 40
OPEN_KEY = QuestionKey("run-open", "2026-11-10T11:00:00+00:00")
SETTLED_KEY = QuestionKey("run-settled", "2026-11-10T11:05:00+00:00")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


def _scratch(root: Path, name: str, now: datetime) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "input.json").write_text("x", encoding="utf-8")
    stamp = (now - timedelta(days=OLD_DAYS)).timestamp()
    os.utime(directory / "input.json", (stamp, stamp))
    os.utime(directory, (stamp, stamp))
    return directory


def _claim(
    store: Store, key: QuestionKey, answering_run_id: str, now: datetime
) -> None:
    with store.write() as transaction:
        insert_question(
            transaction,
            claimed_question(key, member_id=CORE, answering_run_id=answering_run_id),
            now=now,
        )


def _status(
    store: Store, tmp_path: Path, core_dir: Path, prune_fn: Prune | None = None
) -> StatusResult:
    state = tmp_path / "state"
    deps = status_deps(
        tmp_path,
        cf=FakeCf({core_dir: CORE}),
        runs=[],
        names=NAMES,
        answering_dir=state / "answering",
    )
    layout = StateLayout(
        state_home=state,
        store_path=state / "amoeba.sqlite3",
        answering_dir=deps.answering_dir,
        logs_dir=deps.logs_dir,
        calls_log_dir=deps.calls_log_dir,
        legacy_home=None,
    )

    def real_prune(target: Store, *, now: datetime, after_days: int) -> PruneReport:
        return prune(target, layout, now, after_days)

    deps = replace(deps, prune=real_prune if prune_fn is None else prune_fn)
    result = status(store, user_config(), {}, directory=core_dir, deps=deps)
    return result


def test_status_prunes_settled_and_orphan_scratch_and_keeps_an_open_ones(
    store: Store, tmp_path: Path
) -> None:
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    probe = status_deps(tmp_path, cf=FakeCf({}), runs=[], names=NAMES).clock()
    answering = tmp_path / "state" / "answering"
    _claim(store, OPEN_KEY, "scratch-open", probe)
    _claim(store, SETTLED_KEY, "scratch-settled", probe)
    dismissed = dismiss(
        store,
        {"run_id": SETTLED_KEY.run_id, "reason": "done"},
        clock=lambda: probe,
    )
    assert dismissed.outcome.value == "dismissed"
    kept = _scratch(answering, "scratch-open", probe)
    settled = _scratch(answering, "scratch-settled", probe)
    orphan = _scratch(answering, "scratch-orphan", probe)

    result = _status(store, tmp_path, core_dir)

    assert kept.exists()
    assert not settled.exists()
    assert not orphan.exists()
    assert result.file_problems == ()


def test_prune_problems_reach_status_file_problems(
    store: Store, tmp_path: Path
) -> None:
    core_dir = tmp_path / "core"
    core_dir.mkdir()

    def failing(target: Store, *, now: datetime, after_days: int) -> PruneReport:
        return PruneReport(removed=0, problems=("prune: cannot remove a file",))

    result = _status(store, tmp_path, core_dir, failing)

    assert result.file_problems == ("prune: cannot remove a file",)


def test_status_passes_the_configured_age(store: Store, tmp_path: Path) -> None:
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    seen: list[int] = []

    def recording(target: Store, *, now: datetime, after_days: int) -> PruneReport:
        seen.append(after_days)
        return PruneReport(removed=0, problems=())

    _status(store, tmp_path, core_dir, recording)

    assert seen == [user_config().prune_after_days]


def test_handle_pause_prunes_once_and_after_the_resume(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        resumes_at_prune: list[int] = []

        def recording(target: Store, *, now: datetime, after_days: int) -> PruneReport:
            resumes_at_prune.append(len(w.spawned.resumes))
            return PruneReport(removed=0, problems=())

        w.deps = replace(w.deps, prune=recording)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED
        assert len(w.spawned.resumes) == 1
        assert resumes_at_prune == [1]


def test_handle_pause_puts_prune_problems_in_the_detail(tmp_path: Path) -> None:
    with world(tmp_path) as w:

        def failing(target: Store, *, now: datetime, after_days: int) -> PruneReport:
            return PruneReport(removed=0, problems=("prune: cannot remove a file",))

        w.deps = replace(w.deps, prune=failing)

        result = handle_pause(
            w.store, w.config, RUN, directory=w.directory, deps=w.deps
        )

        assert result.detail is not None
        assert "prune: cannot remove a file" in result.detail


def test_a_prune_store_failure_after_a_resume_is_a_note_not_an_error(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:

        def failing(target: Store, *, now: datetime, after_days: int) -> PruneReport:
            raise StoreBusyError("the store is locked")

        w.deps = replace(w.deps, prune=failing)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED
        assert len(w.spawned.resumes) == 1
        assert result.detail is not None
        assert "prune: the store is locked" in result.detail
