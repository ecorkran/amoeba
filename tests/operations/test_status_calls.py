"""``status``: ``last_call`` on a missed hook and ``file_problems`` (slice 228, D11)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fake_sq import RUN_FILE, SQUADRON_FIXTURES
from store.decision_support import CORE, LINT, seed_programs
from store.question_support import claimed_question
from user_configs import user_config

from amoeba.operations.calls_log import append_call, day_file, result_entry
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.status import StatusResult, status
from amoeba.operations.status_models import RunEntry
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from operations.pause_support import START
from operations.status_support import (
    FakeCf,
    in_directory,
    recorded_run,
    status_deps,
)

PAUSED = "demo-pause-1"
RUNNING = "run-20261111-p6-fe470d63"
NAMES = {CORE: "core-name", LINT: "lint-name"}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


@pytest.fixture
def core_dir(tmp_path: Path) -> Path:
    path = tmp_path / "core"
    path.mkdir()
    return path


def _write_sdk_run_file(tmp_path: Path, run_id: str) -> None:
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    document = json.loads((SQUADRON_FIXTURES / RUN_FILE).read_text(encoding="utf-8"))
    document["execution_mode"] = "sdk"
    (runs / f"{run_id}.json").write_text(json.dumps(document), encoding="utf-8")


def _log_call(tmp_path: Path, run_id: str, outcome: str, reason: str) -> None:
    entry = result_entry(run_id, tmp_path, outcome, reason, "from the hook", START)
    append_call(tmp_path / "logs" / "calls", entry, START)


def _status(store: Store, tmp_path: Path, core_dir: Path) -> StatusResult:
    runs = [
        in_directory(recorded_run(PAUSED), core_dir),
        in_directory(recorded_run(RUNNING), core_dir),
    ]
    deps = status_deps(tmp_path, cf=FakeCf({core_dir: CORE}), runs=runs, names=NAMES)
    return status(store, user_config(), {}, directory=core_dir, deps=deps)


def _entry(result: StatusResult, run_id: str) -> RunEntry:
    (program,) = result.programs
    (member,) = program.members
    (entry,) = [run for run in member.runs if run.run_id == run_id]
    return entry


def test_an_unhandled_run_shows_the_newest_line_the_hook_logged(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _write_sdk_run_file(tmp_path, PAUSED)
    _log_call(tmp_path, PAUSED, "skipped", "not_in_program")

    entry = _entry(_status(store, tmp_path, core_dir), PAUSED)

    assert entry.pause is PauseClass.UNHANDLED
    assert entry.last_call is not None
    assert (entry.last_call.outcome, entry.last_call.reason) == (
        "skipped",
        "not_in_program",
    )
    assert entry.last_call.detail == "from the hook"


def test_an_unhandled_run_the_hook_never_reached_has_a_null_last_call(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _write_sdk_run_file(tmp_path, PAUSED)

    result = _status(store, tmp_path, core_dir)

    assert _entry(result, PAUSED).last_call is None
    assert result.file_problems == ()


def test_a_stale_claim_shows_its_last_call(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    run = in_directory(recorded_run(PAUSED), core_dir)
    assert run.checkpoint is not None
    assert run.checkpoint.paused_at is not None
    key = QuestionKey(run.run_id, run.checkpoint.paused_at)
    with store.write() as transaction:
        insert_question(
            transaction,
            claimed_question(key, member_id=CORE),
            now=START - timedelta(days=1),
        )
    _log_call(tmp_path, PAUSED, "skipped", "already_claimed")

    entry = _entry(_status(store, tmp_path, core_dir), PAUSED)

    assert entry.pause is PauseClass.CLAIM_STALE
    assert entry.last_call is not None
    assert entry.last_call.reason == "already_claimed"


def test_a_run_that_is_not_a_missed_hook_has_no_last_call(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _log_call(tmp_path, RUNNING, "skipped", "not_paused")

    entry = _entry(_status(store, tmp_path, core_dir), RUNNING)

    assert entry.pause is None
    assert entry.last_call is None


def test_a_corrupt_day_file_is_named_in_file_problems_and_the_rest_is_shown(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _write_sdk_run_file(tmp_path, PAUSED)
    _log_call(tmp_path, PAUSED, "skipped", "not_in_program")
    path = day_file(tmp_path / "logs" / "calls", START)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"at": "interrupted')

    result = _status(store, tmp_path, core_dir)

    assert _entry(result, PAUSED).last_call is not None
    (problem,) = result.file_problems
    assert str(path) in problem
