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

import json
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Final, assert_never

from pydantic import BaseModel

from amoeba.config.home import (
    AmoebaHomeError,
    StateLayout,
    config_path,
    squadron_runs_dir,
    state_layout,
)
from amoeba.config.user_config import ConfigError, UserConfig, load_user_config
from amoeba.operations.answer import AnswerOutcome, AnswerResult, answer
from amoeba.operations.decisions import DecisionsOutcome, DecisionsResult, decisions
from amoeba.operations.deps import Deps, production_deps
from amoeba.operations.dismiss import DismissOutcome, DismissResult, dismiss
from amoeba.operations.mark_read import MarkReadOutcome, MarkReadResult, mark_read
from amoeba.operations.members import ContextForgeError
from amoeba.operations.names import Door, OperationName
from amoeba.operations.processes import start_child
from amoeba.operations.prune import prune
from amoeba.operations.prune_models import Prune, PruneReport
from amoeba.operations.resume import resume_bound_seconds
from amoeba.operations.retract import RetractOutcome, RetractResult, retract
from amoeba.operations.set_up import set_up
from amoeba.operations.set_up_models import SetUpOutcome, SetUpResult
from amoeba.operations.state_move import open_state_store
from amoeba.operations.status import StatusOutcome, StatusResult, status
from amoeba.store.errors import StoreError
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs

__all__ = [
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
    "invoke",
    "is_rejected",
    "load_config",
    "open_store",
    "result_document",
    "start_child",
]

#: The bundle of injectable edges the operations take (``operations.deps.Deps``).
OperationDeps = Deps

#: The failures a door reports as ``<ExceptionName>: <message>`` and an exit-3 or
#: ``isError`` answer: config, home, Context Forge, Squadron and store failures.
OPERATIONAL_ERRORS: Final = (
    AmoebaHomeError,
    ConfigError,
    ContextForgeError,
    SquadronError,
    StoreError,
)

#: What ``invoke`` returns: the in-process operations' results.
type OperationResult = (
    SetUpResult
    | AnswerResult
    | StatusResult
    | DecisionsResult
    | MarkReadResult
    | DismissResult
    | RetractResult
)


def load_config() -> UserConfig:
    """The user config from the config home.

    Raises:
        ConfigError: The file is missing or has a bad or unknown key.
        AmoebaHomeError: ``AMOEBA_HOME`` is set but empty or relative.
    """
    return load_user_config(config_path())


def open_store(layout: StateLayout) -> Store:
    """The store at the state home, after any legacy move (228 D2)."""
    return open_state_store(layout)


def _prune_in(layout: StateLayout) -> Prune:
    """``prune`` with the layout bound, so the operations never see the environment."""

    def prune_layout(store: Store, *, now: datetime, after_days: int) -> PruneReport:
        return prune(store, layout, now, after_days)

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


def _required_directory(name: OperationName, directory: Path | None) -> Path:
    if directory is None:
        raise ValueError(f"{name.value} needs the caller's directory")
    return directory


def invoke(
    name: OperationName, document: object, directory: Path | None, door: Door
) -> OperationResult:
    """Run the in-process operation ``name`` on ``document`` and return its result.

    Opens the store (after the legacy move), places the arguments exactly as the CLI
    always has, and closes the store whether the operation returns or raises.
    ``directory`` is the caller's checkout: required by ``set_up`` and ``status``,
    ignored by the others. ``door`` is the interface that carried the call.

    Raises:
        ValueError: ``name`` is ``handle_pause`` (the CLI's own body), or a
            directory-taking operation got none.
        OPERATIONAL_ERRORS: As the operation raises them.
    """
    layout = state_layout()
    with open_store(layout) as store:
        match name:
            case OperationName.SET_UP:
                return set_up(
                    store,
                    load_config(),
                    document,
                    directory=_required_directory(name, directory),
                    run=subprocess.run,
                )
            case OperationName.ANSWER:
                return answer(
                    store,
                    load_config(),
                    document,
                    deps=default_deps(layout),
                    via=door,
                )
            case OperationName.STATUS:
                return status(
                    store,
                    load_config(),
                    document,
                    directory=_required_directory(name, directory),
                    deps=default_deps(layout),
                )
            case OperationName.DECISIONS:
                return decisions(store, document, deps=default_deps(layout))
            case OperationName.MARK_READ:
                return mark_read(store, document)
            case OperationName.DISMISS:
                return dismiss(store, document, clock=default_deps(layout).clock)
            case OperationName.RETRACT:
                return retract(store, document, clock=default_deps(layout).clock)
            case OperationName.HANDLE_PAUSE:
                raise ValueError(
                    f"{name.value} is not run in-process: it is the CLI's own body"
                )
            case _:
                assert_never(name)


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


def result_document(result: OperationResult) -> dict[str, object]:
    """``result`` as the JSON document both doors give: enums are strings."""
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    document: dict[str, object] = json.loads(json.dumps(asdict(result)))
    return document


def is_rejected(result: OperationResult) -> bool:
    """Whether the operation refused the request (the CLI's exit 1)."""
    match result:
        case (
            SetUpResult(outcome=SetUpOutcome.REJECTED)
            | AnswerResult(outcome=AnswerOutcome.REJECTED)
            | StatusResult(outcome=StatusOutcome.REJECTED)
            | DecisionsResult(outcome=DecisionsOutcome.REJECTED)
            | MarkReadResult(outcome=MarkReadOutcome.REJECTED)
            | DismissResult(outcome=DismissOutcome.REJECTED)
            | RetractResult(outcome=RetractOutcome.REJECTED)
        ):
            return True
        case _:
            return False
