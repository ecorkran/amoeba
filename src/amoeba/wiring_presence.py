"""The step and ``cf`` side of ``amoeba-mcp``'s session tick (slices 241, 263 D1, D3).

``amoeba.mcp`` reaches nothing but ``wiring`` and the operations' types (226 D10), so
the synchronous bodies its worker threads run live here: the caller gather, the two
session step calls and what names the way a tick went. The tick never opens a store:
the steps it runs do (``steps_for``), in the thread that calls it. The types and
errors presence passes around are re-exported from here for the same reason.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

from amoeba.client.client_file import load_client_file
from amoeba.client.errors import (
    ClientFileError,
    HubCertificateError,
    HubRefusedError,
    HubUnreachableError,
)
from amoeba.config.home import AmoebaHomeError, client_file_path, pinned_cert_path
from amoeba.config.user_config import ConfigError
from amoeba.operations.deps import Deps
from amoeba.operations.errors import ContextForgeError
from amoeba.operations.here import gather_caller
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.steps.models_session import (
    SESSION_END,
    SESSION_TICK,
    SessionEndRequest,
    SessionTickReply,
    SessionTickRequest,
    TickEntry,
)
from amoeba.operations.store_steps import Steps
from amoeba.store.errors import StoreBusyError, StoreError
from amoeba.store.vocabulary import DeliveryEvent, MessageKind
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.wire.protocol import SessionIdentity
from amoeba.wiring_steps import (
    AFTER_STEP_ERRORS,
    DoorSteps,
    LastReply,
    run_after_step,
)

__all__ = [
    "AFTER_STEP_ERRORS",
    "AmoebaHomeError",
    "CfRun",
    "ClientFileError",
    "ConfigError",
    "ContextForgeError",
    "DeliveryEvent",
    "Deps",
    "HereCaller",
    "HereNotAProject",
    "HubCertificateError",
    "HubRefusedError",
    "HubUnreachableError",
    "LastReply",
    "MessageKind",
    "SessionIdentity",
    "SessionTickReply",
    "SessionTickRequest",
    "StepSource",
    "Steps",
    "StoreBusyError",
    "StoreError",
    "TickEntry",
    "end_session",
    "gather_here",
    "machine_name",
    "run_after_step",
    "tick_session",
    "way_of",
]

#: Opens the steps one worker thread uses and closes them when the thread is done: a
#: sqlite connection cannot cross threads, so a ``Steps`` never does either. Each
#: thread passes its own ``LastReply`` and the session's identity (the door sends it as
#: headers, D6).
type StepSource = Callable[
    [LastReply, SessionIdentity | None], AbstractContextManager[Steps]
]

#: The two ways a tick goes (263 D1): a step number of one is unrelated to the other.
WAY_DOOR = "door"
WAY_LOCAL = "local"
#: The machine a session on the local way runs as.
LOCAL_MACHINE_NAME = "local"


def gather_here(directory: Path, cf_run: CfRun) -> HereCaller | HereNotAProject:
    """The directory's Context Forge project (D3); one ``cf`` call.

    Raises:
        ContextForgeError: ``cf`` failed or timed out.
    """
    return gather_caller(directory, cf_run)


def tick_session(steps: Steps, request: SessionTickRequest) -> SessionTickReply:
    """One ``session_tick`` step."""
    return steps.run(SESSION_TICK, request)


def end_session(steps: Steps, session_id: str) -> None:
    """One ``session_end`` step; an id with no row is done."""
    steps.run(SESSION_END, SessionEndRequest(session_id=session_id))


def way_of(steps: Steps) -> str:
    """Which way ``steps`` goes: the door or the local store."""
    return WAY_DOOR if isinstance(steps, DoorSteps) else WAY_LOCAL


def machine_name() -> str:
    """The client file's machine name, or ``local``.

    Raises:
        ClientFileError: The client file or the saved certificate does not load.
    """
    path = client_file_path()
    if not path.exists():
        return LOCAL_MACHINE_NAME
    return load_client_file(path, pinned_cert_path()).machine
