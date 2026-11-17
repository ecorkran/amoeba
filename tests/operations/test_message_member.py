"""``resolve_caller`` and ``resolve_recipient`` with the stub ``cf`` (slice 240, D3)."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT, fake_cf_run
from store.message_support import NOW, seed_members

from amoeba.operations.members import ContextForgeError
from amoeba.operations.message_member import (
    Caller,
    Recipient,
    Refusal,
    UnknownActor,
    resolve_actor,
    resolve_caller,
    resolve_recipient,
)
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.programs import remove_member
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfRun
from operations.set_up_support import RECORDED_ID, RECORDED_NAME, FakeCf

DIRECTORY = Path("/work/checkout")
OTHER_ID = "other-project-id"
OTHER_NAME = "other-project-name"
STRANGER = "stranger-project"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, RECORDED_ID, OTHER_ID)
        yield opened


def _cf(directory_fixture: str = DEFAULT_WORKTREE) -> FakeCf:
    return FakeCf(
        directory_fixture=directory_fixture, projects=[(OTHER_ID, OTHER_NAME)]
    )


def _timeout(argv: Sequence[str], **_kwargs: object) -> None:
    raise subprocess.TimeoutExpired(list(argv), 1.0)


def test_a_directory_in_a_member_is_the_caller(store: Store) -> None:
    cf = _cf()

    caller = resolve_caller(store, DIRECTORY, None, cf)

    assert caller == Caller(RECORDED_ID)
    assert len(cf.calls) == 1


@pytest.mark.parametrize("explicit", [RECORDED_ID, RECORDED_NAME])
def test_an_explicit_member_naming_the_same_member_is_accepted(
    store: Store, explicit: str
) -> None:
    cf = _cf()

    caller = resolve_caller(store, DIRECTORY, explicit, cf)

    assert caller == Caller(RECORDED_ID)
    assert len(cf.calls) == 2


def test_an_explicit_member_naming_another_is_a_mismatch_under_the_directorys(
    store: Store,
) -> None:
    caller = resolve_caller(store, DIRECTORY, OTHER_NAME, _cf())

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.MEMBER_MISMATCH
    assert caller.record_under == RECORDED_ID
    assert OTHER_NAME in caller.detail


@pytest.mark.parametrize("explicit", [OTHER_ID, OTHER_NAME])
def test_a_directory_in_no_project_takes_the_explicit_member(
    store: Store, explicit: str
) -> None:
    caller = resolve_caller(store, DIRECTORY, explicit, _cf(OUTSIDE_ANY_PROJECT))

    assert caller == Caller(OTHER_ID)


def test_a_project_in_no_program_takes_the_explicit_member(tmp_path: Path) -> None:
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        with store.write() as transaction:
            seed_members(transaction, OTHER_ID)

        caller = resolve_caller(store, DIRECTORY, OTHER_NAME, _cf())

    assert caller == Caller(OTHER_ID)


def test_no_member_anywhere_is_not_a_member_and_records_nothing(
    store: Store,
) -> None:
    caller = resolve_caller(store, DIRECTORY, None, _cf(OUTSIDE_ANY_PROJECT))

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.NOT_A_MEMBER
    assert caller.record_under is None
    assert "no Context Forge project" in caller.detail


def test_an_explicit_member_that_is_no_active_member_is_not_a_member(
    store: Store,
) -> None:
    caller = resolve_caller(store, DIRECTORY, STRANGER, _cf(OUTSIDE_ANY_PROJECT))

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.NOT_A_MEMBER
    assert STRANGER in caller.detail


def test_an_actor_resolution_gives_an_unknown_actor_when_no_member_is_named(
    store: Store,
) -> None:
    outside = _cf(OUTSIDE_ANY_PROJECT)

    assert resolve_actor(store, DIRECTORY, None, outside) == UnknownActor()


def test_an_actor_resolution_refuses_an_explicit_member_that_is_no_member(
    store: Store,
) -> None:
    actor = resolve_actor(store, DIRECTORY, STRANGER, _cf(OUTSIDE_ANY_PROJECT))

    assert isinstance(actor, Refusal)
    assert actor.code is RejectCode.NOT_A_MEMBER
    assert actor.record_under is None
    assert STRANGER in actor.detail


def test_an_actor_resolution_still_refuses_a_mismatch(store: Store) -> None:
    caller = resolve_actor(store, DIRECTORY, OTHER_NAME, _cf())

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.MEMBER_MISMATCH
    assert caller.record_under == RECORDED_ID


@pytest.mark.parametrize("run", [fake_cf_run(None), _timeout])
def test_a_cf_failure_or_timeout_propagates_for_the_directory(
    store: Store, run: CfRun
) -> None:
    with pytest.raises(ContextForgeError):
        resolve_caller(store, DIRECTORY, None, run)


def test_a_cf_failure_on_the_explicit_member_propagates(store: Store) -> None:
    cf = _cf()

    def failing_on_reference(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if "-p" in argv:
            return fake_cf_run(None)(argv)
        return cf(argv, **kwargs)

    with pytest.raises(ContextForgeError):
        resolve_caller(store, DIRECTORY, OTHER_NAME, failing_on_reference)


@pytest.mark.parametrize("reference", [OTHER_ID, OTHER_NAME])
def test_a_name_and_an_id_both_resolve_a_recipient(
    store: Store, reference: str
) -> None:
    recipient = resolve_recipient(store, reference, _cf())

    assert isinstance(recipient, Recipient)
    assert recipient.member_id == OTHER_ID


def test_an_unregistered_recipient_is_unknown(store: Store) -> None:
    recipient = resolve_recipient(store, STRANGER, _cf())

    assert isinstance(recipient, Refusal)
    assert recipient.code is RejectCode.UNKNOWN_RECIPIENT
    assert STRANGER in recipient.detail
    assert recipient.record_under is None


def test_a_removed_recipient_is_unknown(store: Store) -> None:
    with store.write() as transaction:
        assert remove_member(transaction, OTHER_ID, NOW)

    recipient = resolve_recipient(store, OTHER_NAME, _cf())

    assert isinstance(recipient, Refusal)
    assert recipient.code is RejectCode.UNKNOWN_RECIPIENT


@pytest.mark.parametrize("run", [fake_cf_run(None), _timeout])
def test_a_cf_failure_or_timeout_propagates_for_the_recipient(
    store: Store, run: CfRun
) -> None:
    with pytest.raises(ContextForgeError):
        resolve_recipient(store, OTHER_NAME, run)
