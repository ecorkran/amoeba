"""The types the served operations share: the result union, the edges a hub part
reads from outside the store, what the client gathered and what a call needs gathered
(slice 261, D5, D12). Split from ``served`` to keep it under its size."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from amoeba.config.user_config import UserConfig
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


class HereKind(StrEnum):
    """Which gathered shape an operation needs (D5)."""

    CALLER = "caller"
    CHECKOUT = "checkout"


@dataclass(frozen=True)
class Gather:
    """What a call needs the client to gather."""

    here: HereKind | None = None
    runs: bool = False


NOTHING_GATHERED: Final = Gather()
CALLER_GATHER: Final = Gather(here=HereKind.CALLER)
