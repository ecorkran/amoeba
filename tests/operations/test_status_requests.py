"""Requests and rejected calls in ``status`` and ``list`` (slice 240, D11, D12)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from store.decision_support import CORE, LINT, seed_programs
from store.message_support import TTL, delivery_rows, send_request
from user_configs import user_config

from amoeba.operations.deps import Deps
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.status import StatusResult, status
from amoeba.operations.status_models import MemberStatus, StatusOutcome
from amoeba.store.message_rejections import record_rejection
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from operations.list_support import ListCf, names_of, project_entry
from operations.release_support import SettableClock
from operations.status_support import CfAnswer, status_deps

ELSEWHERE = Path("/work/elsewhere")
PROJECTS = [project_entry(CORE, "core-name"), project_entry(LINT, "lint-name")]
CONFIG = user_config()
SHORT_BUSY_TIMEOUT_SECONDS = 0.2


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(
        tmp_path / "amoeba.sqlite3", busy_timeout_seconds=SHORT_BUSY_TIMEOUT_SECONDS
    ) as opened:
        seed_programs(opened)
        yield opened


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def deps(tmp_path: Path, clock: SettableClock) -> Deps:
    cf = ListCf(PROJECTS, {ELSEWHERE: CfAnswer.NOT_A_PROJECT})
    base = status_deps(tmp_path, cf=cf, runs=[], names=names_of(PROJECTS))
    return replace(base, clock=clock)


def _status(store: Store, deps: Deps) -> StatusResult:
    return status(store, CONFIG, {}, directory=ELSEWHERE, deps=deps)


def _members(result: StatusResult) -> dict[str, MemberStatus]:
    return {m.member.id: m for p in result.programs for m in p.members}


def _send(store: Store, request_id: str) -> None:
    with store.write() as transaction:
        send_request(transaction, request_id, from_member=CORE, to_member=LINT)


def test_a_chain_shows_direction_ages_and_child_ids(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _send(store, "root")
    clock.now += timedelta(hours=1)
    with store.write() as transaction:
        send_request(
            transaction,
            "child",
            from_member=LINT,
            to_member=CORE,
            parent_id="root",
            parent_depth=1,
            now=clock.now,
        )
    clock.now += timedelta(hours=1)

    result = _status(store, deps)

    core = _members(result)[CORE]
    lint = _members(result)[LINT]
    root, child = core.requests
    assert (root.id, root.direction.value, root.other_member, root.other_name) == (
        "root",
        "sent",
        LINT,
        "lint-name",
    )
    assert root.subject == "subject of root"
    assert root.state is RequestState.OPEN
    assert root.child_ids == ("child",)
    assert (child.id, child.direction.value, child.parent_id) == (
        "child",
        "received",
        "root",
    )
    assert child.child_ids == ()
    assert child.created_at - root.created_at == timedelta(hours=1)
    assert [r.id for r in lint.requests] == ["root", "child"]


def test_a_finished_request_is_not_shown_and_child_ids_hold_only_live_children(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _send(store, "root")
    with store.write() as transaction:
        send_request(
            transaction,
            "child",
            from_member=LINT,
            to_member=CORE,
            parent_id="root",
            parent_depth=1,
        )
        message = get_message(transaction, "child")
        assert message is not None
        change_state(
            transaction,
            message,
            RequestState.DONE,
            DeliveryEvent.DONE,
            CORE,
            clock.now,
            StateFields(),
        )

    result = _status(store, deps)

    (root,) = _members(result)[CORE].requests
    assert root.child_ids == ()


def test_rejected_calls_are_shown_under_the_caller_newest_first(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    with store.write() as transaction:
        for number, code in enumerate(("unknown_recipient", "id_reused")):
            record_rejection(
                transaction,
                CORE,
                "send",
                f"to-{number}",
                f"id-{number}",
                None,
                code,
                f"detail {number}",
                clock.now + timedelta(minutes=number),
            )

    result = _status(store, deps)

    core, lint = _members(result)[CORE], _members(result)[LINT]
    assert [call.code for call in core.rejected_calls] == [
        "id_reused",
        "unknown_recipient",
    ]
    first = core.rejected_calls[0]
    assert (first.operation, first.to_ref, first.message_id, first.detail) == (
        "send",
        "to-1",
        "id-1",
        "detail 1",
    )
    assert lint.rejected_calls == ()


def test_the_notice_is_set_only_when_something_shows(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    assert _status(store, deps).notice is None
    _send(store, "ask")
    assert _status(store, deps).notice == QUOTED_DATA_NOTICE


def test_a_rejected_call_alone_sets_the_notice(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    with store.write() as transaction:
        record_rejection(
            transaction,
            CORE,
            "reply",
            None,
            "ask",
            None,
            "unknown_request",
            "d",
            clock.now,
        )

    assert _status(store, deps).notice == QUOTED_DATA_NOTICE


def test_an_expired_request_is_swept_and_leaves_the_list(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _send(store, "ask")
    clock.now += TTL

    result = _status(store, deps)

    assert _members(result)[CORE].requests == ()
    with store.read() as transaction:
        stored = get_message(transaction, "ask")
        assert stored is not None and stored.state is RequestState.EXPIRED
        assert [row[3] for row in delivery_rows(transaction)] == ["expired", "expired"]


def test_a_held_store_gives_a_problem_and_the_call_still_returns_expired(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _send(store, "ask")
    clock.now += TTL
    with closing(sqlite3.connect(store.path, isolation_level=None)) as holder:
        holder.execute("BEGIN IMMEDIATE")

        result = _status(store, deps)

    assert result.outcome is StatusOutcome.LISTED
    assert result.sweep_problem is not None
    assert "message sweep did not run" in result.sweep_problem
    (request,) = _members(result)[CORE].requests
    assert request.state is RequestState.EXPIRED


def test_the_status_keys_gain_only_the_notice_and_the_two_member_fields(
    store: Store, deps: Deps
) -> None:
    document = _status(store, deps).model_dump(mode="json")

    assert set(document) == {
        "outcome",
        "rejection",
        "notice",
        "programs",
        "unplaced_runs",
        "closed_now",
        "sweep_problem",
        "file_problems",
        "problems",
    }
    member = document["programs"][0]["members"][0]
    assert set(member) == {
        "member",
        "runs",
        "waiting_on_pm",
        "requests",
        "rejected_calls",
    }
