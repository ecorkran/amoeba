"""The session tick: the member lookup and the row it keeps (slice 263, D2, D3, D5)."""

import logging
import subprocess
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

import anyio
import pytest
from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT, fake_cf_run
from store_open import open_local_store

from amoeba.mcp.presence import (
    UNRECOGNIZED_CLIENT,
    client_name,
)
from amoeba.mcp.tick import CF_REASK_SECONDS
from amoeba.store.checkouts import delete_checkouts_of_member
from amoeba.store.row_values import encode_timestamp
from mcp_server.presence_rig import (
    FAST,
    MEMBER_ID,
    FakeClock,
    Opener,
    RecordingOutbound,
    all_session_rows,
    eventually,
    make_deps,
    member_state,
    sessions_in,
    timed_out_cf,
)
from mcp_server.tick_rig import (
    CLIENT,
    replied,
    run_tick,
    setup,
    warnings_of,
)

# --- the member lookup (D3) ------------------------------------------------------


class CountingCf:
    """A ``cf`` that answers with ``fixture`` (swappable), fails the first
    ``failures`` calls, and counts its calls."""

    def __init__(self, fixture: str | None, failures: int = 0) -> None:
        self.fixture = fixture
        self.failures = failures
        self.calls = 0

    def __call__(
        self, argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls += 1
        if self.calls <= self.failures:
            return fake_cf_run(None)(argv, **kwargs)
        return fake_cf_run(self.fixture)(argv, **kwargs)


def test_a_cf_that_fails_twice_then_answers_gives_a_row_at_the_third_tick(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cf = CountingCf(DEFAULT_WORKTREE, failures=2)
    state, deps, _ = setup(store_path, tmp_path, cf_run=cf)

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")

    with caplog.at_level(logging.INFO):
        anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    assert cf.calls == 3
    assert len([m for m in warnings_of(caplog) if "ContextForgeError" in m]) == 1
    assert any(r.getMessage() == "tick recovered" for r in caplog.records)


def test_a_cf_that_hangs_ends_each_tick_with_one_warning(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[int] = []

    def hanging(argv: Sequence[str], **kwargs: object) -> Any:
        calls.append(1)
        return timed_out_cf(argv, **kwargs)

    state, deps, _ = setup(store_path, tmp_path, cf_run=hanging)

    async def scenario() -> None:
        await eventually(lambda: len(calls) >= 4, "several ticks")

    with caplog.at_level(logging.WARNING):
        anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    assert len([m for m in warnings_of(caplog) if "tick failed" in m]) == 1
    assert state.resolved.is_set()
    assert all_session_rows(store_path) == []


def test_a_directory_that_is_not_a_project_asks_cf_once_per_reask_time(
    store_path: Path, tmp_path: Path
) -> None:
    cf = CountingCf(OUTSIDE_ANY_PROJECT)
    clock = FakeClock()
    opener = Opener(store_path)
    state = member_state(clock, tmp_path)
    deps = make_deps(opener, clock, cf_run=cf)

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 4, "ticks that do not ask again")
        assert cf.calls == 1
        assert state.member_id is None
        assert state.off_reason
        clock.advance(CF_REASK_SECONDS)
        await eventually(lambda: cf.calls == 2, "the ask once it is that old")

    anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    assert all_session_rows(store_path) == []


def test_a_non_member_directory_logs_its_reason_once_across_many_ticks(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    opener = Opener(store_path)
    state = member_state(clock, tmp_path)
    deps = make_deps(opener, clock, cf_run=CountingCf(OUTSIDE_ANY_PROJECT))

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 4, "several ticks")

    with caplog.at_level(logging.INFO):
        anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    (line,) = [
        r.getMessage() for r in caplog.records if "no presence" in r.getMessage()
    ]
    assert f"{tmp_path} is not a member" in line


def test_after_add_the_row_appears_within_the_reask_time_and_after_rm_the_row_goes(
    store_path: Path, tmp_path: Path
) -> None:
    cf = CountingCf(OUTSIDE_ANY_PROJECT)
    clock = FakeClock()
    opener = Opener(store_path)
    state = member_state(clock, tmp_path)
    deps = make_deps(opener, clock, cf_run=cf)

    async def scenario() -> None:
        await eventually(lambda: cf.calls == 1, "the first ask")
        cf.fixture = DEFAULT_WORKTREE
        clock.advance(CF_REASK_SECONDS)
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")
        with open_local_store(store_path) as store, store.write() as transaction:
            delete_checkouts_of_member(transaction, MEMBER_ID)
        await eventually(lambda: not all_session_rows(store_path), "the row removed")
        await eventually(lambda: state.member_id is None, "the member gone")

    anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)


def test_a_repo_not_added_yet_is_a_tick_with_no_member_and_no_row(
    store_path: Path, tmp_path: Path
) -> None:
    with open_local_store(store_path) as store, store.write() as transaction:
        delete_checkouts_of_member(transaction, MEMBER_ID)
    state, deps, _ = setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(replied(state), "a reply")

    anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    assert state.member_id is None
    assert state.off_reason is not None
    assert all_session_rows(store_path) == []


# --- the row the tick keeps (D2, D5) ---------------------------------------------


def test_the_first_tick_writes_the_row_with_the_client_name(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")

    anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    (session,) = sessions_in(store_path, deps.clock(), FAST.session_stale_seconds)
    assert session.session_id == state.session_id
    assert session.member_id == MEMBER_ID
    assert session.client == CLIENT
    assert session.directory == str(tmp_path)
    assert session.started_at == session.heartbeat_at == deps.clock()
    assert session.push_confirmed_at is None


def test_a_bad_client_name_is_stored_as_the_placeholder(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")

    anyio.run(
        run_tick, deps, state, RecordingOutbound(), scenario, client_name("bad\x00name")
    )

    (row,) = all_session_rows(store_path)
    assert row[1] == UNRECOGNIZED_CLIENT


def test_a_process_suspended_past_the_stale_limit_gets_its_row_back(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = setup(store_path, tmp_path)
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock)
    started = clock()

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "first row")
        woke = started + timedelta(seconds=FAST.session_stale_seconds + 30)
        clock.now = woke
        await eventually(
            lambda: (
                [row[3] for row in all_session_rows(store_path)]
                == [encode_timestamp(woke)]
            ),
            "the row written again at the hub's time",
        )

    anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    (session,) = sessions_in(store_path, clock(), FAST.session_stale_seconds)
    assert session.started_at == session.heartbeat_at == clock()


def test_a_push_confirmation_reaches_the_row_at_the_next_tick(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")
        state.push_confirmed_at = deps.clock()
        await eventually(
            lambda: any(row[4] for row in all_session_rows(store_path)),
            "the confirmation written",
        )

    anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    (session,) = sessions_in(store_path, deps.clock(), FAST.session_stale_seconds)
    assert session.push_confirmed_at == deps.clock()
