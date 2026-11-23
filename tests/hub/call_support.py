"""A throwaway hub and request builders for the call tests (slice 260)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from store.decision_support import seed_programs
from user_configs import user_config

from amoeba.config.home import StateLayout, layout_under
from amoeba.config.user_config import UserConfig
from amoeba.hub.call_refusals import CallReply
from amoeba.hub.calls import CallRequest, DoorHooks, handle_call
from amoeba.hub.store_open import open_hub_store
from amoeba.store.machines import (
    ActingMachine,
    hash_token,
    invite_machine,
    machine_for_token,
)
from amoeba.store.store import Store
from amoeba.wire.protocol import (
    DOCUMENT_KEY,
    HEADER_AUTHORIZATION,
    HEADER_CALL_ID,
    HEADER_CLIENT_VERSION,
    HEADER_DOOR_VERSION,
    Reply,
    parse_reply,
)
from amoeba.wire.times import DOOR_VERSION

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
CLIENT_VERSION = "0.2.3"
ALPHA_TOKEN = "alpha-token-for-the-call-tests"
BETA_TOKEN = "beta-token-for-the-call-tests"


def layout_in(root: Path) -> StateLayout:
    state = root / "state"
    return layout_under(state, root / "config", None)


@dataclass
class HubRig:
    """A hub store with machines ``alpha`` and ``beta``, seeded as ``alpha``."""

    layout: StateLayout
    clock_now: datetime = NOW
    config: Callable[[], UserConfig] = user_config

    def clock(self) -> datetime:
        return self.clock_now

    def advance(self, **delta: float) -> None:
        self.clock_now += timedelta(**delta)

    def open_store(self) -> Store:
        return open_hub_store(self.layout)

    def call(
        self,
        name: str,
        document: object,
        *,
        token: str | None = ALPHA_TOKEN,
        call_id: str = "call-1",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        hooks: DoorHooks = DoorHooks(),  # noqa: B008
    ) -> CallReply:
        return handle_call(
            make_request(name, document, token, call_id, body, headers),
            open_store=self.open_store,
            clock=self.clock,
            load_config=self.config,
            hooks=hooks,
        )

    def machine(self, token: str) -> ActingMachine | None:
        with self.open_store() as store, store.read() as transaction:
            return machine_for_token(transaction, hash_token(token))

    def rows(self, query: str) -> list[tuple[object, ...]]:
        with self.open_store() as store, store.read() as transaction:
            return [tuple(row) for row in transaction.execute(query)]


def make_request(
    name: str,
    document: object,
    token: str | None,
    call_id: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> CallRequest:
    sent = {
        HEADER_DOOR_VERSION: str(DOOR_VERSION),
        HEADER_CLIENT_VERSION: CLIENT_VERSION,
        HEADER_CALL_ID: call_id,
    }
    if token is not None:
        sent[HEADER_AUTHORIZATION] = f"Bearer {token}"
    sent.update(headers or {})
    payload = (
        json.dumps({DOCUMENT_KEY: document}).encode("utf-8") if body is None else body
    )
    return CallRequest(name=name, headers=sent, body=payload, peer="127.0.0.1:50000")


def build_rig(root: Path) -> HubRig:
    """A migrated hub store with two invited machines and two programs seeded."""
    rig = HubRig(layout_in(root))
    with open_hub_store(rig.layout, create=True) as store:
        with store.write() as transaction:
            invite_machine(transaction, "alpha", hash_token(ALPHA_TOKEN), NOW)
            invite_machine(transaction, "beta", hash_token(BETA_TOKEN), NOW)
        with store.read() as transaction:
            alpha = machine_for_token(transaction, hash_token(ALPHA_TOKEN))
        assert alpha is not None
        store.act_as(alpha)
        seed_programs(store)
    return rig


def result_of(reply: CallReply) -> Reply:
    parsed = parse_reply(reply.body)
    assert parsed is not None, reply.body
    return parsed
