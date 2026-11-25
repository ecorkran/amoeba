"""Live sessions in ``status`` and ``list`` (slice 241, D6, D8, 10.2).

Kept apart from ``test_status_requests.py`` (240's), which is near its size guide;
the same seeding and deps.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from store.decision_support import CORE, LINT, seed_programs
from store.seed import insert_member
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.deps import Deps
from amoeba.operations.list_view import ListResult
from amoeba.operations.status import StatusResult
from amoeba.operations.status_models import MemberStatus
from amoeba.store.models import Session
from amoeba.store.programs import remove_member
from amoeba.store.sessions import live_member_ids, upsert_session
from amoeba.store.store import Store
from amoeba.wire.times import DOOR_VERSION
from operations.list_support import ListCf, project_entry
from operations.release_support import SettableClock
from operations.status_placed import list_view, status
from operations.status_support import CfAnswer, status_deps

ELSEWHERE = Path("/work/elsewhere")
PROJECTS = [project_entry(CORE, "core-name"), project_entry(LINT, "lint-name")]
CONFIG = user_config()
STALE = timedelta(seconds=CONFIG.session_stale_seconds)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def deps(tmp_path: Path, clock: SettableClock) -> Deps:
    cf = ListCf(PROJECTS, {ELSEWHERE: CfAnswer.NOT_A_PROJECT})
    base = status_deps(tmp_path, cf=cf, runs=[])
    return replace(base, clock=clock)


def _session(
    session_id: str,
    member_id: str,
    now: datetime,
    *,
    started: timedelta = timedelta(minutes=10),
    beat: timedelta = timedelta(seconds=5),
    confirmed: bool = False,
) -> Session:
    return Session(
        session_id=session_id,
        member_id=member_id,
        client="claude-code",
        directory=f"/work/{member_id}",
        started_at=now - started,
        heartbeat_at=now - beat,
        push_confirmed_at=now - beat if confirmed else None,
        client_version="9.9.9",
        door_version=DOOR_VERSION,
    )


def _write(store: Store, *sessions: Session) -> None:
    with store.write() as transaction:
        for session in sessions:
            upsert_session(transaction, session)


def _status(store: Store, deps: Deps) -> StatusResult:
    return status(store, CONFIG, {}, directory=ELSEWHERE, deps=deps)


def _members(result: StatusResult) -> dict[str, MemberStatus]:
    return {m.member.id: m for p in result.programs for m in p.members}


def test_a_fresh_session_shows_with_its_fields(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    session = _session("s1", CORE, clock.now, confirmed=True)
    _write(store, session)

    (entry,) = _members(_status(store, deps))[CORE].sessions

    assert entry.client == session.client
    assert entry.directory == session.directory
    assert entry.started_at == session.started_at
    assert entry.heartbeat_at == session.heartbeat_at
    assert entry.push_confirmed_at == session.push_confirmed_at


def test_one_members_sessions_are_oldest_first(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _write(
        store,
        _session("young", CORE, clock.now, started=timedelta(minutes=1)),
        _session("old", CORE, clock.now, started=timedelta(hours=2)),
    )

    entries = _members(_status(store, deps))[CORE].sessions

    assert [entry.started_at for entry in entries] == sorted(
        entry.started_at for entry in entries
    )
    assert entries[0].started_at == clock.now - timedelta(hours=2)


def test_a_stale_session_and_a_removed_members_session_do_not_show(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _write(
        store,
        _session("stale", CORE, clock.now, beat=STALE),
        _session("of-removed", LINT, clock.now),
    )
    with store.write() as transaction:
        assert remove_member(transaction, LINT, clock.now)

    members = _members(_status(store, deps))

    assert members[CORE].sessions == ()
    assert LINT not in members


def test_sessions_alone_set_no_notice(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _write(store, _session("s1", CORE, clock.now))

    result = _status(store, deps)

    assert result.notice is None
    assert _members(result)[CORE].sessions


def test_list_document_equals_status_with_sessions(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _write(store, _session("s1", CORE, clock.now, confirmed=True))

    listed = list_view(store, CONFIG, {}, directory=ELSEWHERE, deps=deps)
    expected = _status(store, deps)

    assert isinstance(listed, ListResult)
    assert listed.document() == expected.model_dump(mode="json")
    assert _members(expected)[CORE].sessions


def test_live_member_ids_matches_the_confirmed_fresh_sessions_status_shows(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    # 244's contract: one store, one clock, every kind of row.
    with store.write() as transaction:
        for member in ("member-unconfirmed", "member-stale", "member-removed"):
            insert_member(
                transaction,
                project_id=member,
                program_id="trading",
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=clock.now,
                updated_at=clock.now,
            )
    _write(
        store,
        _session("confirmed", CORE, clock.now, confirmed=True),
        _session("unconfirmed", "member-unconfirmed", clock.now),
        _session("stale", "member-stale", clock.now, beat=STALE, confirmed=True),
        _session("removed", "member-removed", clock.now, confirmed=True),
    )
    with store.write() as transaction:
        assert remove_member(transaction, "member-removed", clock.now)
    wide = deps

    shown = {
        member_id
        for member_id, member in _members(_status(store, wide)).items()
        if any(entry.push_confirmed_at is not None for entry in member.sessions)
    }
    with store.read() as transaction:
        live = live_member_ids(
            transaction, clock.now, CONFIG.session_stale_seconds, DOOR_VERSION
        )

    assert live == shown == {CORE}
