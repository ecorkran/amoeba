"""A store with a machine's waiting work, and the steps to claim it (slice 262, D10).

Rows are seeded through the store functions on a throwaway store: ``local`` is the
calling machine and ``beta`` another one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from store.question_support import (
    ANSWERING_RUN,
    KEY,
    MEMBER_ID,
    NOW,
    claimed_question,
    insert_held_row,
    seed_members,
)
from store.seed import insert_checkout, mark_wake_wanted
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.limits import (
    pause_claim_seconds,
    resume_claim_seconds,
)
from amoeba.operations.steps.models import CLAIM_WORK
from amoeba.operations.steps.models_work import ClaimWorkReply, ClaimWorkRequest
from amoeba.operations.steps.work import work_waiting
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.answers import add_pm_answer
from amoeba.store.machines import ActingMachine, invite_machine, the_owner
from amoeba.store.messages import insert_request
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.wire.times import DOOR_VERSION

CONFIG = user_config()
LOGS = "/state/logs"
RESUME_LIMIT = timedelta(seconds=resume_claim_seconds(CONFIG))
PAUSE_LIMIT = timedelta(seconds=pause_claim_seconds(CONFIG))
START_WAIT = timedelta(seconds=CONFIG.answering_wait_seconds)


def key_n(number: int) -> QuestionKey:
    return QuestionKey(f"run-{number}", f"2026-11-10T{number:02d}:00:00+00:00")


@dataclass
class Rig:
    """The store, the test clock and both machines."""

    store: Store
    now: datetime
    local: ActingMachine
    beta: ActingMachine

    def steps(self) -> LocalSteps:
        return LocalSteps(self.store, StepEdges(lambda: self.now, lambda: CONFIG))

    def claim(self) -> ClaimWorkReply:
        return self.steps().run(CLAIM_WORK, ClaimWorkRequest(logs_dir=LOGS))

    def waiting(self, machine: ActingMachine | None = None) -> bool:
        target = self.local if machine is None else machine
        with self.store.read() as transaction:
            return work_waiting(
                transaction, target.machine_id, CONFIG, self.now, DOOR_VERSION
            )

    def as_machine(self, machine: ActingMachine) -> None:
        self.store.act_as(machine)

    def advance(self, by: timedelta) -> None:
        self.now += by


def open_rig(path: Path) -> Rig:
    """A store with two members and the machines ``local`` and ``beta``."""
    store = open_local_store(path)
    seed_members(store)
    with store.write() as transaction:
        invite_machine(transaction, "beta", "d" * 64, NOW)
        beta_id = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'beta'"
            ).fetchone()[0]
        )
        owner = the_owner(transaction)
        local_id = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'local'"
            ).fetchone()[0]
        )
    return Rig(
        store, NOW, ActingMachine(local_id, owner), ActingMachine(beta_id, owner)
    )


def seed_as(rig: Rig, machine: ActingMachine, seed: Callable[[], object]) -> None:
    """Run ``seed`` with ``machine`` as the acting machine, then back as ``local``."""
    rig.as_machine(machine)
    try:
        seed()
    finally:
        rig.as_machine(rig.local)


def answered_question(rig: Rig, number: int, text: str = "an answer") -> int:
    """An answered question with a PM answer and no outcome; the answer's seq."""
    key = key_n(number)
    with rig.store.write() as transaction:
        insert_question(
            transaction, claimed_question(key, answering_run_id=f"a-{number}"), now=NOW
        )
        return add_pm_answer(transaction, key, text, now=NOW, via=None)


def claimed_row(rig: Rig, number: int, *, at: datetime = NOW) -> QuestionKey:
    key = key_n(number)
    with rig.store.write() as transaction:
        insert_question(
            transaction,
            claimed_question(key, answering_run_id=f"claim-{number}"),
            now=at,
        )
    return key


def held_row(rig: Rig, number: int, request_id: str, *, done: bool) -> QuestionKey:
    """A held question whose request is ``done`` (or still open)."""
    key = key_n(number)
    with rig.store.write() as transaction:
        insert_request(
            transaction,
            message_id=request_id,
            from_member=MEMBER_ID,
            to_member="member-b",
            parent_id=None,
            parent_depth=None,
            subject="s",
            body="b",
            ttl=timedelta(days=30),
            now=NOW,
        )
        if done:
            transaction.execute(
                "UPDATE messages SET state = 'done', result = 'r' WHERE message_id = ?",
                (request_id,),
            )
        insert_held_row(transaction, key, request_id=request_id)
    return key


def wakeable_member(rig: Rig, cf_id: str = "cf-wakeable") -> None:
    """The member with a checkout and a wake command here and a wake due for it."""
    with rig.store.write() as transaction:
        insert_checkout(
            transaction,
            member_id="member-b",
            cf_project_id=cf_id,
            path="/work/b",
            wake_command="wake-agent",
            now=NOW,
        )
        mark_wake_wanted(transaction, "member-b", NOW)


__all__ = [
    "ANSWERING_RUN",
    "CONFIG",
    "KEY",
    "LOGS",
    "PAUSE_LIMIT",
    "RESUME_LIMIT",
    "START_WAIT",
    "Rig",
    "answered_question",
    "claimed_row",
    "held_row",
    "key_n",
    "open_rig",
    "seed_as",
    "wakeable_member",
]
