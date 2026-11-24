"""The types the served operations share: the result union, the edges a hub part
reads from outside the store, what the client gathered and what a call needs gathered
(slice 261, D5, D12). Split from ``served`` to keep it under its size."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from amoeba.config.user_config import UserConfig
from amoeba.operations.answer import AnswerRecorded
from amoeba.operations.changes_models import ChangesResult
from amoeba.operations.decisions import DecisionsResult
from amoeba.operations.deps import Deps
from amoeba.operations.dismiss import DismissResult
from amoeba.operations.here_document import (
    Here,
)
from amoeba.operations.list_registry import (
    DependenciesView,
    MembersView,
    ProgramsView,
    StandingView,
)
from amoeba.operations.list_view import ListResult
from amoeba.operations.mark_read import MarkReadResult
from amoeba.operations.message_results import (
    CancelResult,
    InboxResult,
    ReplyResult,
    SendResult,
)
from amoeba.operations.report_release_models import ReportReleaseResult
from amoeba.operations.retract import RetractResult
from amoeba.operations.runs_document import RunsDocument
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.standing_models import StandingResult, WithdrawResult
from amoeba.operations.status import StatusResult
from amoeba.operations.steps.models_runs import OpenRunsReply
from amoeba.store.vocabulary import Door

type ServedResult = (
    DecisionsResult
    | MarkReadResult
    | DismissResult
    | RetractResult
    | StandingResult
    | WithdrawResult
    | SetUpResult
    | ListResult
    | ProgramsView
    | MembersView
    | DependenciesView
    | StandingView
    | StatusResult
    | InboxResult
    | ReplyResult
    | CancelResult
    | SendResult
    | ChangesResult
    | ReportReleaseResult
    | AnswerRecorded
)


@dataclass(frozen=True)
class ServedEdges:
    """What the served operations read from outside the store."""

    clock: Callable[[], datetime]
    #: Called only by an operation that needs config (``needs_config``).
    load_config: Callable[[], UserConfig]
    #: The machine's own edges, present with no client file. ``None`` on the hub, which
    #: starts no wake and no run, sweeps no question and prunes nothing: those read and
    #: change the files of the machine that ran ``sq`` (261 D9, D11).
    local: Deps | None = None


@dataclass(frozen=True)
class ClientValues:
    """What the client part gathered, parsed: the caller's project (or the checkout,
    for ``add``) and the machine's runs. ``None`` for what the call does not need."""

    here: Here | None = None
    runs: RunsDocument | None = None
    #: What ``open_runs`` said when the client asked for the runs document: the
    #: client part reuses it for the prune after the hub part (262 D9, D12).
    open_runs: OpenRunsReply | None = None
    #: ``answer``'s door as the client states it (262 D7).
    via: Door | None = None
    #: The calling machine's logs directory, for a wake ``send`` claims (262 D8).
    logs_dir: Path | None = None


class HereKind(StrEnum):
    """Which gathered shape an operation needs (D5)."""

    CALLER = "caller"
    CHECKOUT = "checkout"


@dataclass(frozen=True)
class Gather:
    """What a call needs the client to gather."""

    here: HereKind | None = None
    runs: bool = False
    #: The door the call came through (``answer``).
    via: bool = False
    #: The calling machine's logs directory (``send``).
    logs_dir: bool = False


NOTHING_GATHERED: Final = Gather()
CALLER_GATHER: Final = Gather(here=HereKind.CALLER)
#: The body keys of ``via`` and ``logs_dir``; ``wire.protocol`` holds them again, and a
#: test asserts they agree.
VIA_KEY: Final = "via"
LOGS_DIR_KEY: Final = "logs_dir"
#: ``send``: the caller, and the logs directory a claimed wake's logs go under.
SEND_GATHER: Final = Gather(here=HereKind.CALLER, logs_dir=True)
#: ``answer``: the door it came through.
ANSWER_GATHER: Final = Gather(via=True)
