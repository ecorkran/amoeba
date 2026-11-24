"""The two ways a client-run command reaches the store, for tests that run one body
both ways (262 D16): in process on a local store, or through a joined client's door
to an in-process hub."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from hub.call_support import ALPHA_TOKEN, HubRig
from hub.in_process_hub import InProcessHub
from hub.join_support import line_for
from store_open import open_local_store

from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.store_steps import LocalSteps, Steps
from amoeba.store.store import Store
from amoeba.wiring_door import join
from amoeba.wiring_steps import DoorSteps, LastReply

LOCAL = "local"
DOOR = "door"
WAYS = (LOCAL, DOOR)


@contextmanager
def store_for(way: str, tmp_path: Path) -> Generator[tuple[Store, HubRig | None]]:
    """The local store, or a hub's store acting as ``alpha``, the machine this test's
    home is joined as; the hub's rig comes with it."""
    if way == LOCAL:
        with open_local_store(tmp_path / "amoeba.sqlite3") as store:
            yield store, None
        return
    with InProcessHub(tmp_path / "hub") as hub:
        join(line_for(hub), set_aside_local=False)
        alpha = hub.rig.machine(ALPHA_TOKEN)
        assert alpha is not None
        with hub.rig.open_store() as store:
            store.act_as(alpha)
            yield store, hub.rig


def steps_on(way: str, store: Store, edges: StepEdges) -> Steps:
    """The steps a command on that way uses: in process on ``store``, or the door's."""
    return LocalSteps(store, edges) if way == LOCAL else DoorSteps(LastReply())
