"""A recipient with a wake command, fake spawn and clock, for ``send``'s wake step
(slice 244, D2, D5)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT, fixture_document
from user_configs import user_config

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.inbox import inbox
from amoeba.operations.message_results import InboxResult, SendResult
from amoeba.operations.processes import WaitableChild
from amoeba.operations.reply import reply
from amoeba.operations.send import send
from amoeba.store.store import Store
from amoeba.upstream.squadron.launch import LaunchError
from operations.message_support import (
    RECIPIENT,
    RECIPIENT_NAME,
    message_cf,
    message_deps,
)
from operations.pause_support import FakeChild, SpawnRecorder
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY

#: Context Forge's ``projectPath`` for every project the stub ``cf`` knows.
CHECKOUT = Path(str(fixture_document(DEFAULT_WORKTREE)["projectPath"]))
SCRIPT = Path("/installed/bin/amoeba")
COMMAND = "wake-agent --max-seconds 60"
#: A member registered in the store that Context Forge does not know: its reference
#: is read as an id, so ``send`` has no checkout path for it.
GHOST = "ghost-member-id"
MAX_WAKES = 2
TICK = timedelta(microseconds=1)


def wake_config(max_wakes_per_day: int = MAX_WAKES) -> UserConfig:
    return user_config().model_copy(update={"max_wakes_per_day": max_wakes_per_day})


@dataclass
class WakeRig:
    """The deps of one test with the spawner and clock kept for assertions."""

    deps: Deps
    spawner: SpawnRecorder
    clock: SettableClock


def wake_rig(
    tmp_path: Path,
    *,
    script: Callable[[], Path] | None = None,
    results: list[WaitableChild | LaunchError] | None = None,
) -> WakeRig:
    """Deps whose ``spawn`` records its calls (and returns ``results`` in turn)."""
    clock = SettableClock()
    scripted: list[WaitableChild | LaunchError] = results or [FakeChild(None)]
    spawner = SpawnRecorder(scripted)
    base = message_deps(tmp_path, clock)
    deps = replace(base, spawn=spawner, amoeba_script=script or (lambda: SCRIPT))
    return WakeRig(deps, spawner, clock)


def give_command(
    store: Store, member: str = RECIPIENT, command: str | None = COMMAND
) -> None:
    with store.write() as transaction:
        transaction.execute(
            "UPDATE members SET wake_command = ? WHERE project_id = ?",
            (command, member),
        )


def send_request(
    store: Store,
    rig: WakeRig,
    request_id: str,
    *,
    config: UserConfig | None = None,
    to: str = RECIPIENT_NAME,
    **fields: object,
) -> SendResult:
    document = {
        "id": request_id,
        "to": to,
        "subject": f"subject of {request_id}",
        "body": f"body of {request_id}",
        **fields,
    }
    return send(
        store, config or wake_config(), document, directory=DIRECTORY, deps=rig.deps
    )


def inbox_of(
    store: Store, rig: WakeRig, member_name: str, *, since: int | None = None
) -> InboxResult:
    """``inbox`` for ``member_name`` from a directory that belongs to no member;
    with ``since``, the deliveries after it too."""
    deps = replace(rig.deps, cf_run=message_cf(OUTSIDE_ANY_PROJECT))
    document: dict[str, object] = {"member": member_name}
    if since is not None:
        document["since"] = since
    return inbox(store, document, directory=DIRECTORY, deps=deps)


def accept(store: Store, rig: WakeRig, request_id: str, member_name: str) -> None:
    """The recipient accepts ``request_id``, so an agent is on it."""
    deps = replace(rig.deps, cf_run=message_cf(OUTSIDE_ANY_PROJECT))
    reply(
        store,
        wake_config(),
        {"id": request_id, "action": "accept", "member": member_name},
        directory=DIRECTORY,
        deps=deps,
    )


def at(rig: WakeRig, moment: datetime) -> None:
    rig.clock.now = moment
