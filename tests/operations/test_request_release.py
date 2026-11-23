"""``start_ended_held``: the start trigger for held questions (slice 242, D7, 6.3)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from store.question_support import (
    MEMBER_ID,
    OTHER_MEMBER_ID,
    insert_held_row,
    seed_members,
)
from store_open import open_local_store
from user_configs import user_config

from amoeba.amoeba_script import AmoebaScriptMissing
from amoeba.operations import request_release
from amoeba.operations.request_release import (
    MAX_STARTS_PER_CALL,
    REQUEST_RELEASE_LOG_DIRECTORY,
    START_FAILED_OUTCOME,
    start_ended_held,
)
from amoeba.store.errors import StoreBusyError
from amoeba.store.held_questions import mark_start_attempted
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.notes import NewNote, insert_note
from amoeba.store.questions import get_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState, RequestState
from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.launch import LaunchError
from operations.held_support import seed_request
from operations.pause_support import START, DepsRig, FakeChild, build_deps

CONFIG = user_config()
WAIT = timedelta(seconds=CONFIG.answering_wait_seconds)
SCRIPT = Path("/installed/bin/amoeba")
CHECKOUT = Path("/work/a")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _found_script() -> Path:
    return SCRIPT


def _rig(
    tmp_path: Path,
    store: Store,
    *,
    amoeba_script: Callable[[], Path] = _found_script,
) -> DepsRig:
    """Deps whose spawn first takes a write on ``store``: no transaction is open."""

    def take_a_write() -> None:
        with store.write():
            pass

    rig = build_deps(tmp_path, polls={}, spawns=[FakeChild(0)], on_spawn=take_a_write)
    rig.deps = replace(rig.deps, amoeba_script=amoeba_script)
    return rig


def _key(number: int) -> QuestionKey:
    return QuestionKey(f"run-{number}", "2026-11-10T11:00:00+00:00")


def _held(
    store: Store,
    number: int,
    state: RequestState | None,
    *,
    held_at: timedelta = timedelta(0),
    ttl: timedelta = timedelta(days=30),
    sent_at: timedelta = timedelta(0),
) -> QuestionKey:
    """A held row on its own request in ``state`` (``None``: no request row)."""
    request_id = f"request-{number}"
    if state is not None:
        seed_request(
            store,
            state,
            request_id=request_id,
            from_member=MEMBER_ID,
            to_member=OTHER_MEMBER_ID,
            now=START + sent_at,
            ttl=ttl,
        )
    key = _key(number)
    with store.write() as transaction:
        insert_held_row(transaction, key, request_id=request_id, now=START + held_at)
    return key


def _row(store: Store, key: QuestionKey) -> QuestionRecord:
    with store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None
    return row


def _started_run_ids(rig: DepsRig) -> list[str]:
    return [call.argv[-1] for call in rig.spawner.calls]


def _call_lines(rig: DepsRig) -> list[dict[str, object]]:
    lines: list[dict[str, object]] = []
    for day in sorted(rig.deps.calls_log_dir.glob("*.jsonl")):
        lines += [json.loads(line) for line in day.read_text().splitlines()]
    return lines


@pytest.mark.parametrize(
    "state",
    [RequestState.DONE, RequestState.DECLINED, RequestState.CANCELLED, None],
)
def test_a_row_whose_request_ended_or_is_gone_is_started(
    tmp_path: Path, store: Store, state: RequestState | None
) -> None:
    key = _held(store, 1, state)
    rig = _rig(tmp_path, store)

    start_ended_held(store, CONFIG, rig.deps)

    (call,) = rig.spawner.calls
    assert call.argv == (str(SCRIPT), "handle-pause", "--json", "--", key.run_id)
    assert call.cwd == CHECKOUT
    assert call.logs.stdout.parent == rig.deps.logs_dir / REQUEST_RELEASE_LOG_DIRECTORY
    assert call.logs.stdout.name.startswith(f"{key.run_id}-")
    assert call.logs.stdout.name.endswith(".stdout.log")
    assert call.logs.stderr.name.endswith(".stderr.log")
    assert _row(store, key).start_attempted_at == START


def test_an_open_request_past_its_ttl_is_started_with_no_sweep(
    tmp_path: Path, store: Store
) -> None:
    _held(
        store, 1, RequestState.OPEN, sent_at=-timedelta(days=2), ttl=timedelta(days=1)
    )
    rig = _rig(tmp_path, store)

    start_ended_held(store, CONFIG, rig.deps)

    assert _started_run_ids(rig) == ["run-1"]


@pytest.mark.parametrize("state", [RequestState.OPEN, RequestState.ACCEPTED])
def test_a_row_whose_request_is_live_is_not_started(
    tmp_path: Path, store: Store, state: RequestState
) -> None:
    key = _held(store, 1, state)
    rig = _rig(tmp_path, store)

    start_ended_held(store, CONFIG, rig.deps)

    assert rig.spawner.calls == []
    assert _row(store, key).start_attempted_at is None


def test_a_recent_attempt_waits_and_an_old_one_is_retried(
    tmp_path: Path, store: Store
) -> None:
    recent = _held(store, 1, RequestState.DONE)
    old = _held(store, 2, RequestState.DONE)
    with store.write() as transaction:
        assert mark_start_attempted(
            transaction, recent, START - WAIT + timedelta(seconds=1), None
        )
        assert mark_start_attempted(transaction, old, START - WAIT, None)
    rig = _rig(tmp_path, store)

    start_ended_held(store, CONFIG, rig.deps)

    assert _started_run_ids(rig) == [old.run_id]


def test_never_attempted_rows_start_before_attempted_ones(
    tmp_path: Path, store: Store
) -> None:
    attempted = _held(store, 0, RequestState.DONE, held_at=-timedelta(days=1))
    with store.write() as transaction:
        assert mark_start_attempted(transaction, attempted, START - 2 * WAIT, None)
    fresh = [
        _held(store, n, RequestState.DONE) for n in range(1, 1 + MAX_STARTS_PER_CALL)
    ]
    rig = _rig(tmp_path, store)

    start_ended_held(store, CONFIG, rig.deps)

    assert _started_run_ids(rig) == [key.run_id for key in fresh]
    assert _row(store, attempted).start_attempted_at == START - 2 * WAIT


def test_at_most_the_cap_starts_and_the_rest_are_untouched(
    tmp_path: Path, store: Store
) -> None:
    keys = [
        _held(store, n, RequestState.DONE, held_at=timedelta(seconds=n))
        for n in range(MAX_STARTS_PER_CALL + 2)
    ]
    rig = _rig(tmp_path, store)

    start_ended_held(store, CONFIG, rig.deps)

    assert _started_run_ids(rig) == [k.run_id for k in keys[:MAX_STARTS_PER_CALL]]
    for key in keys[MAX_STARTS_PER_CALL:]:
        assert _row(store, key).start_attempted_at is None


def test_a_launch_error_is_logged_as_start_failed_and_the_row_stays_held(
    tmp_path: Path, store: Store
) -> None:
    key = _held(store, 1, RequestState.DONE)
    rig = _rig(tmp_path, store)
    rig.spawner.results = [LaunchError(LaunchFailure.SPAWN_ERROR, "no such directory")]

    start_ended_held(store, CONFIG, rig.deps)

    (line,) = _call_lines(rig)
    assert line["outcome"] == START_FAILED_OUTCOME
    assert line["run_id"] == key.run_id
    assert line["directory"] == str(CHECKOUT)
    assert line["detail"] == "no such directory"
    row = _row(store, key)
    assert row.state is QuestionState.WAITING_ON_REQUEST
    assert row.start_attempted_at == START


def test_a_missing_script_writes_an_error_line_per_row_and_raises_nothing(
    tmp_path: Path, store: Store
) -> None:
    keys = [_held(store, n, RequestState.DONE) for n in range(2)]

    def missing() -> Path:
        raise AmoebaScriptMissing("the amoeba script is not at /nowhere/amoeba")

    rig = _rig(tmp_path, store, amoeba_script=missing)

    start_ended_held(store, CONFIG, rig.deps)

    lines = _call_lines(rig)
    assert [line["run_id"] for line in lines] == [k.run_id for k in keys]
    assert {line["error"] for line in lines} == {"AmoebaScriptMissing"}
    assert rig.spawner.calls == []


def test_a_store_error_on_the_read_is_logged_and_not_raised(
    tmp_path: Path,
    store: Store,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _held(store, 1, RequestState.DONE)

    def busy(*_arguments: object) -> list[QuestionRecord]:
        raise StoreBusyError("the store is busy")

    monkeypatch.setattr(request_release, "held_rows", busy)
    rig = _rig(tmp_path, store)

    with caplog.at_level(logging.ERROR):
        start_ended_held(store, CONFIG, rig.deps)

    assert rig.spawner.calls == []
    assert "could not read the held questions" in caplog.text


def test_a_held_row_naming_a_note_is_a_logged_row_error_not_a_silent_skip(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """A note has no state and ``link_for`` never holds a question on one, so the real
    ``effective_state`` refuses the row."""
    note = NewNote("request-1", MEMBER_ID, OTHER_MEMBER_ID, None, "a subject", "a body")
    with store.write() as transaction:
        insert_note(transaction, note, [OTHER_MEMBER_ID], START)
        insert_held_row(transaction, _key(1), request_id="request-1", now=START)
    rig = _rig(tmp_path, store)

    with caplog.at_level(logging.ERROR):
        start_ended_held(store, CONFIG, rig.deps)

    assert rig.spawner.calls == []
    assert "is a note" in caplog.text
