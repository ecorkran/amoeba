"""The door's side of ``wiring``: the mode switch and the steps of `join` and `leave`
(slice 260, D2, D4).

It imports nothing from ``wiring``, which imports it, so there is no cycle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from amoeba.client import join as client_join
from amoeba.client.call import call
from amoeba.client.client_file import ClientFile, load_client_file
from amoeba.client.errors import HubUnreachableError
from amoeba.config.home import (
    STORE_FILE_NAME,
    StateLayout,
    client_file_path,
    pinned_cert_path,
    state_layout,
)
from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.names import OperationName
from amoeba.operations.served import ServedEdges
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.state_move import open_state_store, prepare_state_home
from amoeba.store.set_aside import (
    PutBack,
    SetAsideHooks,
    clear_orphan_side_files,
    holds_closed_mark,
    put_back,
    set_aside,
    set_aside_stores,
)
from amoeba.store.vocabulary import Door
from amoeba.wire.join_line import JoinError, parse_join_line
from amoeba.wire.times import DOOR_VERSION
from amoeba.wiring_gather import body_keys, finish_client_part, gather_values
from amoeba.wiring_results import OperationResult, result_from_document
from amoeba.wiring_steps import DoorSteps, take_work_keys

#: How the two commands are named in a message.
JOIN_COMMAND: Final = "join"
LEAVE_COMMAND: Final = "leave"


def local_served_edges(
    deps: Deps, load_config: Callable[[], UserConfig]
) -> ServedEdges:
    """The edges the served operations get on the local way: the clock, the config
    loader and this machine's own edges (the hub gets none, 261 D9, D11)."""
    return ServedEdges(
        clock=deps.clock,
        load_config=load_config,
        door_version=DOOR_VERSION,
        local=deps,
    )


def joined() -> ClientFile | None:
    """The loaded client file, or ``None`` when this machine has none.

    Checked on every call and never cached. With a client file it also checks the
    saved certificate is there.

    Raises:
        ClientFileError: The file or the saved certificate cannot be used.
    """
    client_path = client_file_path()
    if not client_path.exists():
        return None
    return load_client_file(client_path, pinned_cert_path())


def route(  # noqa: PLR0913 - invoke's arguments, the deps and the door's steps
    name: OperationName,
    document: object,
    directory: Path | None,
    door: Door,
    make_deps: Callable[[], Deps],
    steps: DoorSteps,
) -> OperationResult | None:
    """The hub's result when this machine is joined, ``None`` when it is not.

    A served operation gathers what it needs here (the client part, so a
    ``ContextForgeError`` is raised before any hub call), goes through
    ``client.call`` with the gathered values beside the document, and comes back as
    the typed result the local way returns, after the client part that follows the
    hub part (a resume, a wake, the file clean-up) ran on ``steps``. ``add``'s door
    refusal is returned as the result it is, with no call. With a client file nothing
    local is read or written first. The reply's work keys go into ``steps.last``; a
    call that got no reply marks it unreachable.
    """
    client_file = joined()
    if client_file is None:
        return None
    deps = make_deps()
    values = gather_values(name, document, directory, door, deps, steps)
    if isinstance(values, SetUpResult):
        return values
    try:
        result = call(
            client_file,
            pinned_cert_path(),
            name.value,
            document,
            extra=body_keys(values),
        )
    except HubUnreachableError:
        steps.last.unreachable = True
        raise
    take_work_keys(result, steps.last)
    served = result_from_document(name.value, result, document)
    return finish_client_part(served, steps, deps, values)


# --- join and leave ----------------------------------------------------------


@dataclass(frozen=True)
class JoinReport:
    """What `join` did."""

    machine: str
    address: str
    #: Where the local store went, with ``--set-aside-local``.
    set_aside: Path | None


def _refuse_in_a_hub_home(layout: StateLayout, command: str) -> None:
    """``join`` and ``leave`` change files beside the store (a mark, a set-aside, the
    write-ahead log of a missing store), which must never be a hub's."""
    if layout.hub_file.exists():
        raise JoinError(
            f"this home is a hub's ({layout.hub_file} exists), so `amoeba {command}` "
            "here would change the hub's store files; run it on a client machine"
        )


def _set_aside_local(
    layout: StateLayout, address: str, now: datetime, hooks: SetAsideHooks
) -> Path | None:
    """Between ``hello`` and the client file: set the local store aside, or finish a
    set-aside a stopped `join` left, or do nothing when there is no store."""
    store_path = layout.store_path
    if not store_path.exists():
        aside = set_aside_stores(store_path)
        if not aside:
            return None
        clear_orphan_side_files(store_path)
        return aside[-1]
    return set_aside(store_path, address, now, hooks)


def _migrate_before_marking(layout: StateLayout) -> None:
    """Open the local store once so it is migrated and ``closed_mark`` exists before
    the mark is written, whatever release last opened it. A store that already holds
    the mark was migrated by the run that wrote it, and the opener would refuse it."""
    if layout.store_path.exists() and not holds_closed_mark(layout.store_path):
        open_state_store(layout).close()


def _refuse_a_local_store(layout: StateLayout) -> None:
    """Without ``--set-aside-local`` a local store, in the state home or still in the
    legacy home, stops the join. It only looks: nothing is moved or opened."""
    legacy = layout.legacy_home
    found = [layout.store_path]
    if legacy is not None:
        found.append(legacy / STORE_FILE_NAME)
    existing = next((path for path in found if path.exists()), None)
    if existing is not None:
        raise JoinError(
            f"a local store exists at {existing}; run `amoeba join` again with "
            "--set-aside-local to set it aside (and `amoeba leave` puts it back)"
        )


def join(
    line_text: str,
    *,
    set_aside_local: bool,
    hooks: SetAsideHooks = SetAsideHooks(),  # noqa: B008  frozen, no state to share
) -> JoinReport:
    """`amoeba join <line>`: D4's steps in order.

    Raises:
        JoinError: A hub home, a line that does not parse, a local store without
            ``--set-aside-local``, a fingerprint that does not match, or a set-aside
            store beside a store that is not its original.
        HubUnreachableError, HubRefusedError, HubCertificateError: From the network
            steps.
    """
    layout = state_layout()
    _refuse_in_a_hub_home(layout, JOIN_COMMAND)
    line = parse_join_line(line_text)
    joined_before = layout.client_file.exists()
    if not joined_before and not set_aside_local:
        _refuse_a_local_store(layout)
    aside: list[Path | None] = [None]

    def between() -> None:
        # Everything that changes the local store waits until the hub answered and
        # its fingerprint matched, so a join that fails changes nothing local.
        if not set_aside_local:
            return
        if not joined_before:
            prepare_state_home(layout)
            _migrate_before_marking(layout)
        aside[0] = _set_aside_local(layout, line.address, datetime.now(UTC), hooks)

    machine = client_join.join(
        line,
        client_path=layout.client_file,
        cert_path=layout.pinned_cert,
        between=between,
    )
    return JoinReport(machine=machine, address=line.address, set_aside=aside[0])


def join_address(address: str) -> ClientFile:
    """`amoeba join --address <host:port>`: change only the address; no hub call."""
    layout = state_layout()
    _refuse_in_a_hub_home(layout, JOIN_COMMAND)
    return client_join.change_address(layout.client_file, layout.pinned_cert, address)


@dataclass(frozen=True)
class LeaveReport:
    """What `leave` did; every field may be empty (then it did nothing)."""

    put_back: PutBack
    removed: list[Path]


def leave() -> LeaveReport:
    """`amoeba leave`: put the set-aside store back, delete the client file, delete
    the saved certificate; each skipped when there is nothing to do, and no hub call
    is made, so it works with the hub down. It has no rejected outcome.

    Raises:
        JoinError: This home is a hub's.
    """
    layout = state_layout()
    _refuse_in_a_hub_home(layout, LEAVE_COMMAND)
    restored = put_back(layout.store_path, datetime.now(UTC))
    removed = client_join.remove_client_files(layout.client_file, layout.pinned_cert)
    return LeaveReport(put_back=restored, removed=removed)
