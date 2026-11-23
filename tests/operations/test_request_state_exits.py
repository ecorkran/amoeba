"""Every state a request can be in has an exit, with nobody editing files (slice 240,
D4, D6, D10; the Amoeba design rule "every state has an exit").

``open`` leaves by ``accept``, ``decline``, ``cancel`` (the sender's, or by id from a
session in no member), expiry at the TTL and the removal of either member. ``accepted``
never expires, and leaves by ``done``, ``decline``, ``cancel`` and the removal of
either member. The four terminal states are pruned after ``prune_after_days``. Each
test walks one state to one exit through the operations; none touches a file or SQL.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT
from store.decision_support import CORE, LINT, seed_programs
from store.message_support import delivery_rows, send_request
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.deps import Deps
from amoeba.operations.set_up_models import SetUpOutcome
from amoeba.store.message_sweep import sweep
from amoeba.store.messages import get_message
from amoeba.store.store import Store
from amoeba.store.vocabulary import RequestState
from operations.list_support import ListCf, project_entry
from operations.message_placed import cancel, reply
from operations.message_support import (
    CONFIG,
    RECIPIENT_NAME,
    message_cf,
    message_deps,
    open_message_store,
    send_request_as_sender,
)
from operations.release_support import SettableClock
from operations.rm_placed import rm
from operations.set_up_support import DIRECTORY, FakeCf, run_set_up
from operations.status_placed import list_view
from operations.status_support import CfAnswer, status_deps

TTL = timedelta(hours=CONFIG.request_open_ttl_hours)
RETENTION = timedelta(days=CONFIG.prune_after_days)
ASK = "ask"
ELSEWHERE = Path("/work/elsewhere")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from open_message_store(tmp_path)


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def sender_deps(tmp_path: Path, clock: SettableClock) -> Deps:
    return message_deps(tmp_path, clock)


@pytest.fixture
def addressee_deps(tmp_path: Path, clock: SettableClock) -> Deps:
    """A session in no member: the addressee is named with ``member``."""
    return message_deps(tmp_path, clock, message_cf(OUTSIDE_ANY_PROJECT))


def _state(store: Store, request_id: str = ASK) -> RequestState | None:
    with store.read() as transaction:
        message = get_message(transaction, request_id)
    return None if message is None else message.state


def _terminal(store: Store, request_id: str = ASK) -> RequestState:
    state = _state(store, request_id)
    assert state is not None
    assert state in RequestState.terminal(), state
    return state


def _reply(store: Store, deps: Deps, action: str, **fields: Any) -> None:
    document = {"id": ASK, "action": action, "member": RECIPIENT_NAME, **fields}
    result = reply(store, CONFIG, document, directory=DIRECTORY, deps=deps)
    assert result.rejection is None, result.problems


def _accept(store: Store, deps: Deps) -> None:
    _reply(store, deps, "accept")


def test_open_exits_by_decline(
    store: Store, sender_deps: Deps, addressee_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, ASK)

    _reply(store, addressee_deps, "decline", text="not ours")

    assert _terminal(store) is RequestState.DECLINED


def test_open_exits_by_the_senders_cancel(store: Store, sender_deps: Deps) -> None:
    send_request_as_sender(store, sender_deps, ASK)

    result = cancel(store, CONFIG, {"id": ASK}, directory=DIRECTORY, deps=sender_deps)

    assert result.rejection is None
    assert _terminal(store) is RequestState.CANCELLED


def test_open_exits_by_a_cancel_by_id_from_a_session_in_no_member(
    store: Store, sender_deps: Deps, addressee_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, ASK)

    result = cancel(
        store, CONFIG, {"id": ASK}, directory=DIRECTORY, deps=addressee_deps
    )

    assert result.rejection is None
    assert _terminal(store) is RequestState.CANCELLED


def test_open_exits_by_accept_into_accepted(
    store: Store, sender_deps: Deps, addressee_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, ASK)

    _accept(store, addressee_deps)

    assert _state(store) is RequestState.ACCEPTED


def _finish_done(store: Store, deps: Deps) -> None:
    _reply(store, deps, "done", text="finished")


def _finish_decline(store: Store, deps: Deps) -> None:
    _reply(store, deps, "decline", text="cannot")


@pytest.mark.parametrize(
    "finish", [_finish_done, _finish_decline], ids=["done", "decline"]
)
def test_accepted_exits_by_the_addressee(
    store: Store,
    sender_deps: Deps,
    addressee_deps: Deps,
    finish: Callable[[Store, Deps], None],
) -> None:
    send_request_as_sender(store, sender_deps, ASK)
    _accept(store, addressee_deps)

    finish(store, addressee_deps)

    assert _terminal(store) in {RequestState.DONE, RequestState.DECLINED}


def test_accepted_exits_by_cancel(
    store: Store, sender_deps: Deps, addressee_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, ASK)
    _accept(store, addressee_deps)

    cancel(store, CONFIG, {"id": ASK}, directory=DIRECTORY, deps=sender_deps)

    assert _terminal(store) is RequestState.CANCELLED


def test_every_terminal_state_is_pruned_after_the_retention(
    store: Store, sender_deps: Deps, addressee_deps: Deps, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, ASK)
    _reply(store, addressee_deps, "decline", text="no")
    clock.now += RETENTION + timedelta(days=1)

    with store.write() as transaction:
        sweep(transaction, clock.now, CONFIG.prune_after_days)

    assert _state(store) is None
    with store.read() as transaction:
        assert delivery_rows(transaction) == []


# --- expiry, through list ----------------------------------------------------


@pytest.fixture
def listing_store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


def _list_deps(tmp_path: Path, clock: SettableClock) -> Deps:
    projects = [project_entry(CORE, "core"), project_entry(LINT, "lint")]
    cf = ListCf(projects, {ELSEWHERE: CfAnswer.NOT_A_PROJECT})
    base = status_deps(tmp_path, cf=cf, runs=[])
    return replace(base, clock=clock)


def test_open_exits_by_expiry_which_list_records_and_tells_both_repos(
    listing_store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    with listing_store.write() as transaction:
        send_request(transaction, ASK, from_member=CORE, to_member=LINT, now=clock.now)
    clock.now += timedelta(hours=72)

    list_view(
        listing_store,
        user_config(),
        {},
        directory=ELSEWHERE,
        deps=_list_deps(tmp_path, clock),
    )

    assert _terminal(listing_store) is RequestState.EXPIRED
    with listing_store.read() as transaction:
        assert sorted((row[1], row[3]) for row in delivery_rows(transaction)) == [
            (CORE, "expired"),
            (LINT, "expired"),
        ]


def test_accepted_never_expires_but_still_exits(
    store: Store,
    sender_deps: Deps,
    addressee_deps: Deps,
    clock: SettableClock,
) -> None:
    send_request_as_sender(store, sender_deps, ASK)
    _accept(store, addressee_deps)
    clock.now += TTL * 10
    with store.write() as transaction:
        sweep(transaction, clock.now, 10_000)

    assert _state(store) is RequestState.ACCEPTED

    _reply(store, addressee_deps, "done", text="late but done")
    assert _terminal(store) is RequestState.DONE


# --- the removal of either member, through rm --------------------------------

PROVIDER = "provider-id"
CONSUMER = "consumer-id"
PROJECTS = [(PROVIDER, "provider"), (CONSUMER, "consumer")]
RULES = {"rules_paths": ["CLAUDE.md"]}


@pytest.fixture
def program_store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        result = run_set_up(
            opened,
            {
                "program": "demo",
                "members": [
                    {"project": "provider", **RULES},
                    {"project": "consumer", **RULES},
                ],
            },
            projects=PROJECTS,
        )
        assert result.outcome is SetUpOutcome.APPLIED
        yield opened


@pytest.mark.parametrize("accepted", [False, True], ids=["open", "accepted"])
@pytest.mark.parametrize("removed", ["provider", "consumer"])
def test_removing_either_member_ends_an_open_or_accepted_request(
    program_store: Store, tmp_path: Path, removed: str, accepted: bool
) -> None:
    with program_store.write() as transaction:
        send_request(transaction, ASK, from_member=CONSUMER, to_member=PROVIDER)
    if accepted:
        accepting = message_deps(
            tmp_path,
            SettableClock(),
            FakeCf(directory_fixture=OUTSIDE_ANY_PROJECT, projects=PROJECTS),
        )
        result = reply(
            program_store,
            CONFIG,
            {"id": ASK, "action": "accept", "member": "provider"},
            directory=DIRECTORY,
            deps=accepting,
        )
        assert result.rejection is None
        assert _state(program_store) is RequestState.ACCEPTED

    result = rm(
        program_store,
        user_config(),
        {"members": [removed]},
        directory=DIRECTORY,
        run=FakeCf(directory_fixture=DEFAULT_WORKTREE, projects=PROJECTS),
    )

    assert result.outcome is SetUpOutcome.APPLIED
    assert _terminal(program_store) is RequestState.CANCELLED
