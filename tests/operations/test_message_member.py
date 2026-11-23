"""``resolve_caller`` and ``resolve_recipient`` on the store (slice 240, D3; 261, D6).

The caller is a gathered ``here`` looked up as a checkout on the acting machine; no
``cf`` runs here, so nothing in this file has a ``cf`` stub.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fixture_document
from store.message_support import NOW, seed_members
from store.seed import insert_checkout
from store_open import open_local_store

from amoeba.operations.caller import acting_machine_id
from amoeba.operations.here_document import HereCaller, HereNotAProject
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
from amoeba.store.machines import invite_machine
from amoeba.store.programs import remove_member
from amoeba.store.store import Store
from operations.set_up_support import RECORDED_ID, RECORDED_NAME

OTHER_ID = "other-project-id"
OTHER_NAME = "other-project-name"
STRANGER = "stranger-project"
CHECKOUT = "/work/checkout"

IN_A_MEMBER = HereCaller(project_id=RECORDED_ID)
IN_A_PROJECT_WITH_NO_PROGRAM = HereCaller(project_id="project-in-no-program")
IN_NO_PROJECT = HereNotAProject(
    not_a_project=str(fixture_document(OUTSIDE_ANY_PROJECT)["message"])
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(
                transaction,
                RECORDED_ID,
                OTHER_ID,
                names={RECORDED_ID: RECORDED_NAME, OTHER_ID: OTHER_NAME},
            )
            insert_checkout(
                transaction,
                member_id=RECORDED_ID,
                cf_project_id=RECORDED_ID,
                path=CHECKOUT,
                now=NOW,
            )
        yield opened


def _caller(
    store: Store, here: HereCaller | HereNotAProject, member: str | None
) -> Caller | Refusal:
    with store.read() as transaction:
        return resolve_caller(transaction, acting_machine_id(transaction), here, member)


def _actor(
    store: Store, here: HereCaller | HereNotAProject, member: str | None
) -> Caller | UnknownActor | Refusal:
    with store.read() as transaction:
        return resolve_actor(transaction, acting_machine_id(transaction), here, member)


def _recipient(store: Store, reference: str) -> Recipient | Refusal:
    with store.read() as transaction:
        return resolve_recipient(transaction, acting_machine_id(transaction), reference)


def test_a_checkout_of_a_member_is_the_caller(store: Store) -> None:
    assert _caller(store, IN_A_MEMBER, None) == Caller(RECORDED_ID)


@pytest.mark.parametrize("explicit", [RECORDED_ID, RECORDED_NAME])
def test_an_explicit_member_naming_the_same_member_is_accepted(
    store: Store, explicit: str
) -> None:
    assert _caller(store, IN_A_MEMBER, explicit) == Caller(RECORDED_ID)


def test_an_explicit_member_naming_another_is_a_mismatch_under_the_checkouts(
    store: Store,
) -> None:
    caller = _caller(store, IN_A_MEMBER, OTHER_NAME)

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.MEMBER_MISMATCH
    assert caller.record_under == RECORDED_ID
    assert OTHER_NAME in caller.detail


def test_an_explicit_member_nobody_has_is_a_mismatch_for_a_member_checkout(
    store: Store,
) -> None:
    caller = _caller(store, IN_A_MEMBER, STRANGER)

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.MEMBER_MISMATCH


@pytest.mark.parametrize("explicit", [OTHER_ID, OTHER_NAME])
def test_a_directory_in_no_project_takes_the_explicit_member(
    store: Store, explicit: str
) -> None:
    assert _caller(store, IN_NO_PROJECT, explicit) == Caller(OTHER_ID)


def test_a_project_in_no_program_takes_the_explicit_member(store: Store) -> None:
    caller = _caller(store, IN_A_PROJECT_WITH_NO_PROGRAM, OTHER_NAME)

    assert caller == Caller(OTHER_ID)


def test_no_member_anywhere_is_not_a_member_and_records_nothing(
    store: Store,
) -> None:
    caller = _caller(store, IN_NO_PROJECT, None)

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.NOT_A_MEMBER
    assert caller.record_under is None
    assert "no Context Forge project" in caller.detail


def test_an_explicit_member_that_is_no_active_member_is_not_a_member(
    store: Store,
) -> None:
    caller = _caller(store, IN_NO_PROJECT, STRANGER)

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.NOT_A_MEMBER
    assert STRANGER in caller.detail


def test_the_same_project_id_on_another_machine_is_not_in_a_program(
    store: Store,
) -> None:
    with store.write() as transaction:
        invite_machine(transaction, "beta", "d" * 64, NOW)
        beta = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'beta'"
            ).fetchone()[0]
        )
        caller = resolve_caller(transaction, beta, IN_A_MEMBER, None)

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.NOT_A_MEMBER


def test_an_actor_resolution_gives_an_unknown_actor_when_no_member_is_named(
    store: Store,
) -> None:
    assert _actor(store, IN_NO_PROJECT, None) == UnknownActor()


def test_an_actor_resolution_refuses_an_explicit_member_that_is_no_member(
    store: Store,
) -> None:
    actor = _actor(store, IN_NO_PROJECT, STRANGER)

    assert isinstance(actor, Refusal)
    assert actor.code is RejectCode.NOT_A_MEMBER
    assert actor.record_under is None
    assert STRANGER in actor.detail


def test_an_actor_resolution_still_refuses_a_mismatch(store: Store) -> None:
    caller = _actor(store, IN_A_MEMBER, OTHER_NAME)

    assert isinstance(caller, Refusal)
    assert caller.code is RejectCode.MEMBER_MISMATCH
    assert caller.record_under == RECORDED_ID


@pytest.mark.parametrize("reference", [OTHER_ID, OTHER_NAME, OTHER_NAME.upper()])
def test_a_name_in_any_case_and_an_id_both_resolve_a_recipient(
    store: Store, reference: str
) -> None:
    recipient = _recipient(store, reference)

    assert isinstance(recipient, Recipient)
    assert recipient.member_id == OTHER_ID


def test_an_unregistered_recipient_is_unknown(store: Store) -> None:
    recipient = _recipient(store, STRANGER)

    assert isinstance(recipient, Refusal)
    assert recipient.code is RejectCode.UNKNOWN_RECIPIENT
    assert STRANGER in recipient.detail
    assert recipient.record_under is None


def test_a_removed_recipient_is_unknown(store: Store) -> None:
    with store.write() as transaction:
        assert remove_member(transaction, OTHER_ID, NOW)

    recipient = _recipient(store, OTHER_NAME)

    assert isinstance(recipient, Refusal)
    assert recipient.code is RejectCode.UNKNOWN_RECIPIENT
