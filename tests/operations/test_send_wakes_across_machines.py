"""``send``'s hub part wakes a repo on the machine that has its checkout (slice 262,
D8, 5.2)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.message_support import NOW
from store.seed import insert_checkout

from amoeba.operations.message_models import SendOutcome
from amoeba.operations.steps.limits import wake_limits
from amoeba.store.machines import ActingMachine, invite_machine, the_owner
from amoeba.store.store import Store
from amoeba.store.vocabulary import WakeOutcome
from amoeba.store.wakes import finish_wake, wake_due
from amoeba.wire.times import DOOR_VERSION
from operations.message_support import RECIPIENT, open_message_store
from operations.wake_send_support import (
    TICK,
    WakeRig,
    at,
    give_command,
    send_request,
    wake_config,
    wake_rig,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    for opened in open_message_store(tmp_path):
        give_command(opened)
        yield opened


@pytest.fixture
def rig(tmp_path: Path) -> WakeRig:
    return wake_rig(tmp_path)


def _wake_ids(store: Store) -> list[str]:
    with store.read() as transaction:
        return [row[0] for row in transaction.execute("SELECT wake_id FROM wakes")]


def test_a_wake_send_claims_in_the_call_that_set_the_mark_is_that_marks_wake(
    store: Store, rig: WakeRig
) -> None:
    result = send_request(store, rig, "ask")

    assert result.woke is not None
    assert result.wake_waiting_on == ()
    (wake_id,) = _wake_ids(store)
    assert result.woke.wake_id == wake_id
    assert result.woke.log_stem == str(rig.deps.logs_dir / "wake" / wake_id)
    with store.write() as transaction:
        finish_wake(
            transaction, wake_id, WakeOutcome.EXITED, 0, None, NOW + timedelta(hours=1)
        )
    at(rig, NOW + timedelta(hours=2))
    with store.read() as transaction:
        assert not wake_due(
            transaction,
            RECIPIENT,
            rig.clock.now,
            wake_limits(wake_config(), DOOR_VERSION),
        )


def _only_another_machine_can_wake(store: Store) -> None:
    with store.write() as transaction:
        invite_machine(transaction, "beta", "b" * 64, NOW)
        beta = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'beta'"
            ).fetchone()[0]
        )
        owner = the_owner(transaction)
    give_command(store, RECIPIENT, None)
    here = _acting(store)
    store.act_as(ActingMachine(beta, owner))
    with store.write() as transaction:
        insert_checkout(
            transaction,
            member_id=RECIPIENT,
            cf_project_id="cf-recipient-beta",
            path="/beta/recipient",
            wake_command="wake-agent",
            now=NOW,
        )
    store.act_as(here)


def _acting(store: Store) -> ActingMachine:
    with store.read() as transaction:
        row = transaction.execute(
            "SELECT machine_id, owner_id FROM machines WHERE name = 'local'"
        ).fetchone()
    return ActingMachine(int(row[0]), int(row[1]))


def test_when_only_another_machine_is_wakeable_send_names_it_and_claims_nothing(
    store: Store, rig: WakeRig
) -> None:
    _only_another_machine_can_wake(store)

    result = send_request(store, rig, "ask")

    assert result.outcome is SendOutcome.SENT
    assert result.woke is None
    assert [item.machine for item in result.wake_waiting_on] == ["beta"]
    assert result.wake_waiting_on[0].last_called_at is None
    assert _wake_ids(store) == []
    assert rig.spawner.calls == []


def test_a_wake_waiting_for_another_machine_is_claimed_there_not_here(
    store: Store, rig: WakeRig
) -> None:
    _only_another_machine_can_wake(store)
    send_request(store, rig, "ask")
    at(rig, NOW + TICK)

    with store.read() as transaction:
        here = wake_due(
            transaction,
            RECIPIENT,
            rig.clock.now,
            wake_limits(wake_config(), DOOR_VERSION),
        )

    assert not here
