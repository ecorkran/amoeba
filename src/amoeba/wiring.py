"""What both doors share (slice 226, D4): config, store, deps and ``invoke``.

The CLI and the MCP server are two doors onto the same operations. This module
holds the one place that knows how each operation's arguments are placed (the
store, the config, the document, the directory, the deps and the clock), so a door
only parses its own input and prints or returns the result. It also re-exports the
types a door needs, so ``amoeba.mcp`` imports nothing from ``store``, ``config`` or
``upstream``.

Only ``cli``, ``mcp`` and this module may call ``state_layout()``, ``config_home()``
and ``state_home()``; the store is opened only through ``open_state_store``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Final, assert_never

from amoeba.client.errors import (
    ClientFileError,
    HubCertificateError,
    HubRefusedError,
    HubUnreachableError,
)
from amoeba.config.home import (
    StateLayout,
    config_path,
    squadron_runs_dir,
    state_layout,
)
from amoeba.config.user_config import UserConfig, load_user_config
from amoeba.operations.answer import answer
from amoeba.operations.answering_run import STDERR_LOG_SUFFIX, STDOUT_LOG_SUFFIX
from amoeba.operations.deps import Deps, production_deps
from amoeba.operations.errors import OPERATION_ERRORS
from amoeba.operations.names import Door, OperationName
from amoeba.operations.processes import start_child
from amoeba.operations.prune import prune
from amoeba.operations.prune_models import Prune, PruneReport
from amoeba.operations.resume import LOG_STAMP_FORMAT
from amoeba.operations.resume_timing import resume_bound_seconds
from amoeba.operations.state_move import open_state_store, prepare_state_home
from amoeba.operations.steps.models_runs import OpenRunsReply
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs
from amoeba.wire.join_line import JoinError
from amoeba.wiring_door import (
    NotServedError,
    joined,
    refuse_if_joined,
    route,
)
from amoeba.wiring_gather import place_served
from amoeba.wiring_release import start_after
from amoeba.wiring_results import OperationResult, is_rejected, result_document

__all__ = [
    "NotServedError",
    "OPERATIONAL_ERRORS",
    "DeadlineError",
    "Door",
    "LaunchError",
    "LaunchLogs",
    "OperationDeps",
    "OperationName",
    "OperationResult",
    "Store",
    "UserConfig",
    "answer_bound_seconds",
    "check_deadline",
    "default_deps",
    "detached_logs",
    "invoke",
    "joined",
    "is_rejected",
    "load_config",
    "open_store",
    "prepare_home",
    "refuse_if_joined",
    "result_document",
    "start_child",
]

#: The bundle of injectable edges the operations take (``operations.deps.Deps``).
OperationDeps = Deps

#: The failures a door reports as ``<ExceptionName>: <message>`` and an exit-3 or
#: ``isError`` answer: config, home, Context Forge, Squadron and store failures.
OPERATIONAL_ERRORS: Final = (
    *OPERATION_ERRORS,
    JoinError,
    ClientFileError,
    HubUnreachableError,
    HubCertificateError,
    HubRefusedError,
    NotServedError,
)


def load_config() -> UserConfig:
    """The user config from the config home.

    Raises:
        ConfigError: The file is missing or has a bad or unknown key.
        AmoebaHomeError: ``AMOEBA_HOME`` is set but empty or relative.
    """
    return load_user_config(config_path())


def prepare_home() -> None:
    """Move legacy state to the state home once, before any call is served (228).

    Raises:
        AmoebaHomeError: ``AMOEBA_HOME`` is set but empty or relative.
        StoreBusyError: The legacy store stayed locked past the timeout.
        StoreRelocateError: A copy failed, did not verify, or a move failed.
    """
    prepare_state_home(state_layout())


def open_store(layout: StateLayout) -> Store:
    """The store at the state home, after any legacy move (228 D2)."""
    return open_state_store(layout)


def _prune_in(layout: StateLayout) -> Prune:
    """``prune`` with the layout bound, so the operations never see the environment."""

    def prune_layout(
        open_runs: Callable[[], OpenRunsReply], *, now: datetime
    ) -> PruneReport:
        return prune(open_runs, layout, now)

    return prune_layout


def default_deps(layout: StateLayout) -> Deps:
    """The real edges, with the layout's directories.

    Raises:
        AmoebaHomeError: Squadron's run directory cannot be located.
    """
    return production_deps(
        answering_dir=layout.answering_dir,
        logs_dir=layout.logs_dir,
        calls_log_dir=layout.calls_log_dir,
        squadron_runs_dir=squadron_runs_dir(),
        legacy_home=layout.legacy_home,
        prune=_prune_in(layout),
    )


def invoke(
    name: OperationName, document: object, directory: Path | None, door: Door
) -> OperationResult:
    """Run the in-process operation ``name`` on ``document`` and return its result.

    Opens the store (after the legacy move), places the arguments exactly as the CLI
    always has, and closes the store whether the operation returns or raises.
    ``directory`` is the caller's checkout: required by ``add``, ``rm``, ``list``,
    ``status``, ``report_release``, ``changes`` and the four message operations,
    ignored by the others. ``door`` is
    the interface that carried the call.

    Raises:
        ValueError: ``name`` is ``handle_pause`` (the CLI's own body), or a
            directory-taking operation got none.
        OPERATIONAL_ERRORS: As the operation raises them.
    """
    served = route(
        name, document, directory, door, lambda: default_deps(state_layout())
    )
    if served is not None:
        return served
    layout = state_layout()
    with open_store(layout) as store:
        try:
            return _dispatch(name, document, directory, door, store, layout)
        finally:
            # After the operation's own transactions closed, on every path, a raise
            # included, as in ``handle_pause`` (242 D7); never raises.
            start_after(name, store, load_config, partial(default_deps, layout))


def _dispatch(  # noqa: PLR0913 - invoke's arguments and the store it opened
    name: OperationName,
    document: object,
    directory: Path | None,
    door: Door,
    store: Store,
    layout: StateLayout,
) -> OperationResult:
    """``invoke``'s body: the operation ``name`` on ``document``."""
    match name:
        case OperationName.ANSWER:
            return answer(
                store,
                load_config(),
                document,
                deps=default_deps(layout),
                via=door,
            )
        case (
            OperationName.ADD
            | OperationName.RM
            | OperationName.LIST
            | OperationName.STATUS
            | OperationName.DECISIONS
            | OperationName.MARK_READ
            | OperationName.DISMISS
            | OperationName.RETRACT
            | OperationName.STANDING
            | OperationName.WITHDRAW
            | OperationName.REPORT_RELEASE
            | OperationName.CHANGES
            | OperationName.SEND
            | OperationName.INBOX
            | OperationName.REPLY
            | OperationName.CANCEL
        ):
            # The client part (a ``cf`` failure raises before any store work), then
            # the hub part in process, as ``run_served`` runs it on the hub too.
            return place_served(
                name,
                store,
                document,
                directory,
                door,
                default_deps(layout),
                load_config,
            )
        case OperationName.HANDLE_PAUSE:
            raise ValueError(
                f"{name.value} is not run in-process: it is the CLI's own body"
            )
        case _:
            assert_never(name)


#: Under the logs directory: the logs of operations the MCP server starts detached
#: (226 D6). Old files here are removed by ``prune`` like any other log.
MCP_LOG_DIRECTORY: Final = "mcp"


def detached_logs(
    operation: OperationName, started: datetime, unique: str
) -> LaunchLogs:
    """The stdout and stderr log paths of a detached ``operation`` started at
    ``started``: ``logs/mcp/<operation>/<UTC stamp>-<unique>.{stdout,stderr}.log``.

    Raises:
        AmoebaHomeError: ``AMOEBA_HOME`` is set but empty or relative.
    """
    directory = state_layout().logs_dir / MCP_LOG_DIRECTORY / operation.value
    stem = f"{started.strftime(LOG_STAMP_FORMAT)}-{unique}"
    return LaunchLogs(
        stdout=directory / f"{stem}{STDOUT_LOG_SUFFIX}",
        stderr=directory / f"{stem}{STDERR_LOG_SUFFIX}",
    )


class DeadlineError(Exception):
    """The config lets an ``answer`` run past the MCP call deadline."""


#: Store waits ``answer`` can make before its resume: the legacy-move lock, the
#: store open and the answer's own write transaction, each at most one busy timeout.
ANSWER_STORE_WAITS: Final = 3


def answer_bound_seconds(config: UserConfig) -> float:
    """The longest an ``answer`` call can take (226 D12).

    ``resume_bound_seconds`` (the resume's wait, polls, terminate graces and store
    write) plus the store waits before it. ``answer`` calls no ``cf`` and no other
    ``sq`` command; the polls it makes are inside the resume bound.
    """
    return resume_bound_seconds(config) + ANSWER_STORE_WAITS * BUSY_TIMEOUT_SECONDS


def check_deadline(config: UserConfig, deadline_seconds: float) -> None:
    """Refuse a config whose ``answer`` could outlive the MCP call deadline.

    A call cut off after it recorded an answer and started a resume would report a
    timeout for work that happened, so the bound must be below the deadline.

    Raises:
        DeadlineError: ``answer_bound_seconds`` is not below ``deadline_seconds``;
            the message names ``resume_wait_seconds`` and the largest value allowed.
    """
    bound = answer_bound_seconds(config)
    if bound < deadline_seconds:
        return
    largest = deadline_seconds - (bound - config.resume_wait_seconds)
    raise DeadlineError(
        f"resume_wait_seconds is {config.resume_wait_seconds:g}, so an answer can "
        f"take {bound:g} s, which is not below the MCP call deadline of "
        f"{deadline_seconds:g} s; set resume_wait_seconds below {largest:g}"
    )
