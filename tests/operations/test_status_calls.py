"""``status``: ``last_call`` on a missed hook and ``file_problems`` (slice 228, D11)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fake_sq import RUN_FILE, SQUADRON_FIXTURES
from store.decision_support import CORE, LINT, seed_programs
from store.question_support import claimed_question, insert_held_row
from store_open import open_local_store
from user_configs import user_config

from amoeba.answering.values import DeclineReason
from amoeba.operations.calls_log import append_call, day_file, result_entry
from amoeba.operations.list_view import ListResult
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.status import StatusResult
from amoeba.operations.status_models import MemberStatus, RunEntry
from amoeba.operations.work_start import START_FAILED_OUTCOME
from amoeba.store.held_questions import mark_start_attempted, settle_held_waiting
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState, RequestState
from operations.held_support import seed_request
from operations.pause_support import START
from operations.status_placed import list_view, status
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
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
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
    deps = status_deps(tmp_path, cf=FakeCf({core_dir: CORE}), runs=runs)
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


HELD_REQUEST = "request-held"


def _paused_key(core_dir: Path) -> QuestionKey:
    run = in_directory(recorded_run(PAUSED), core_dir)
    assert run.checkpoint is not None
    assert run.checkpoint.paused_at is not None
    return QuestionKey(run.run_id, run.checkpoint.paused_at)


def _hold(store: Store, core_dir: Path, state: RequestState) -> QuestionKey:
    """The paused run's question held on a request ``CORE`` sent, in ``state``."""
    seed_request(
        store,
        state,
        request_id=HELD_REQUEST,
        from_member=CORE,
        to_member=LINT,
        reason="out of scope" if state is RequestState.DECLINED else None,
    )
    key = _paused_key(core_dir)
    with store.write() as transaction:
        insert_held_row(transaction, key, member_id=CORE, request_id=HELD_REQUEST)
    return key


def _member(result: StatusResult) -> MemberStatus:
    (program,) = [entry for entry in result.programs if entry.members]
    (member,) = [m for m in program.members if m.member.id == CORE]
    return member


def test_a_held_run_shows_its_request_state_and_a_failed_start_as_last_call(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    key = _hold(store, core_dir, RequestState.DONE)
    with store.write() as transaction:
        assert mark_start_attempted(
            transaction, key, START, None, QuestionState.WAITING_ON_REQUEST
        )
    _log_call(tmp_path, PAUSED, START_FAILED_OUTCOME, "")

    result = _status(store, tmp_path, core_dir)

    entry = _entry(result, PAUSED)
    assert entry.pause is PauseClass.WAITING_ON_REQUEST
    assert entry.detail == (
        f"waiting on request {HELD_REQUEST} (done); handle_pause last started "
        f"{START.isoformat()}"
    )
    assert entry.next is None
    assert entry.last_call is not None
    assert entry.last_call.outcome == START_FAILED_OUTCOME
    assert result.notice == QUOTED_DATA_NOTICE
    assert _member(result).waiting_on_pm == ()


def test_a_held_run_never_started_has_no_start_suffix(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _hold(store, core_dir, RequestState.OPEN)

    entry = _entry(_status(store, tmp_path, core_dir), PAUSED)

    assert entry.detail == f"waiting on request {HELD_REQUEST} (open)"
    assert entry.last_call is None


def test_a_question_released_to_the_pm_by_a_decline_carries_the_request_and_notice(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    key = _hold(store, core_dir, RequestState.DECLINED)
    with store.write() as transaction:
        assert settle_held_waiting(
            transaction,
            key,
            reason=DeclineReason.REQUEST_DECLINED,
            detail="out of scope",
            now=START,
        )

    result = _status(store, tmp_path, core_dir)

    (waiting,) = _member(result).waiting_on_pm
    assert waiting.waiting_reason is DeclineReason.REQUEST_DECLINED
    assert waiting.waiting_detail == "out of scope"
    assert waiting.request_id == HELD_REQUEST
    assert result.notice == QUOTED_DATA_NOTICE
    assert _entry(result, PAUSED).pause is PauseClass.WAITING_ON_PM


def test_list_gives_the_status_result_unchanged_with_a_held_run(
    store: Store, tmp_path: Path, core_dir: Path
) -> None:
    _hold(store, core_dir, RequestState.ACCEPTED)
    runs = [in_directory(recorded_run(PAUSED), core_dir)]
    deps = status_deps(tmp_path, cf=FakeCf({core_dir: CORE}), runs=runs)

    listed = list_view(store, user_config(), {}, directory=core_dir, deps=deps)
    expected = status(store, user_config(), {}, directory=core_dir, deps=deps)

    assert isinstance(listed, ListResult)
    assert listed.document() == expected.model_dump(mode="json")
    assert _entry(expected, PAUSED).pause is PauseClass.WAITING_ON_REQUEST
