"""The operations the door serves, run by one function (slice 260, D11; 261, D5, D12).

``run_served`` is used by the local way (``wiring``) and by the hub, so the two never
differ in what an operation does. What an operation reads from outside the store is in
``ServedEdges``: the clock, the config and, only with no client file, the machine's own
edges. Names and member references are store reads (slice 261, D6).

An operation that needs values only the client can read (the caller's project, the
machine's runs) takes them as ``ClientValues``. With no client file the placement
passes them in process; through the door the hub reads them from the body keys ``here``
and ``runs`` with :func:`client_values_from_body`, which refuses a missing or bad one.
This module imports nothing from ``operations.here``, ``naming``, ``run_gather`` or
``add_gather``: it is the hub's, and the hub never runs ``cf``, ``git`` or ``sq``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, TypeAdapter, ValidationError

from amoeba.config.user_config import UserConfig
from amoeba.operations import list_view as list_view_module
from amoeba.operations import rm as rm_module
from amoeba.operations.add import AddRequest, add, names_no_member
from amoeba.operations.cancel import cancel
from amoeba.operations.changes import changes
from amoeba.operations.changes_models import ChangesResult
from amoeba.operations.decisions import DecisionsResult, decisions
from amoeba.operations.deps import Deps
from amoeba.operations.dismiss import DismissResult, dismiss
from amoeba.operations.here_document import (
    HERE_KEY,
    Here,
    HereCaller,
    HereCheckout,
    HereNotAProject,
    parse_here,
)
from amoeba.operations.inbox import inbox
from amoeba.operations.list_registry import (
    DependenciesView,
    MembersView,
    ProgramsView,
    StandingView,
)
from amoeba.operations.list_view import ListRequest, ListResult, ListSubject, list_view
from amoeba.operations.mark_read import MarkReadResult, mark_read
from amoeba.operations.message_results import (
    CancelResult,
    InboxResult,
    ReplyResult,
    SendResult,
)
from amoeba.operations.names import OperationName
from amoeba.operations.reply import reply
from amoeba.operations.report_release import report_release_swept
from amoeba.operations.report_release_models import ReportReleaseResult
from amoeba.operations.retract import RetractResult, retract
from amoeba.operations.rm import rm
from amoeba.operations.runs_document import RUNS_KEY, RunsDocument, parse_runs
from amoeba.operations.send import send
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.standing import standing
from amoeba.operations.standing_models import StandingResult, WithdrawResult
from amoeba.operations.status import StatusResult, status
from amoeba.operations.withdraw import withdraw
from amoeba.store.store import Store

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
_CALLER: Final = Gather(here=HereKind.CALLER)


def _gather_caller_always(document: object) -> Gather:
    return _CALLER


def _gather_status(document: object) -> Gather:
    return Gather(here=HereKind.CALLER, runs=True)


def _gather_add(document: object) -> Gather:
    try:
        request = AddRequest.model_validate(document)
    except ValidationError:
        # Not a valid request: add rejects it as malformed, and needs no gather.
        return NOTHING_GATHERED
    return Gather(here=HereKind.CHECKOUT if names_no_member(request) else None)


def _gather_rm(document: object) -> Gather:
    return _CALLER if rm_module.needs_here(document) else NOTHING_GATHERED


def _gather_list(document: object) -> Gather:
    if not list_view_module.needs_here(document):
        return NOTHING_GATHERED
    return Gather(here=HereKind.CALLER, runs=True)


type _Runner = Callable[[Store, object, ServedEdges, ClientValues], ServedResult]


def _caller(values: ClientValues) -> HereCaller | HereNotAProject:
    here = values.here
    if isinstance(here, HereCaller | HereNotAProject):
        return here
    raise AssertionError("the operation needs the gathered caller; none was parsed")


def _runs(values: ClientValues) -> RunsDocument:
    if values.runs is None:
        raise AssertionError("the operation needs the gathered runs; none was parsed")
    return values.runs


def _decisions(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return decisions(store, document)


def _mark_read(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return mark_read(store, document)


def _dismiss(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return dismiss(store, document, clock=edges.clock)


def _retract(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return retract(store, document, clock=edges.clock)


def _standing(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return standing(
        store,
        document,
        max_chars=edges.load_config().passages_max_chars,
        now=edges.clock(),
    )


def _withdraw(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return withdraw(store, document, now=edges.clock())


def _add(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    here = values.here
    if here is not None and not isinstance(here, HereCheckout | HereNotAProject):
        raise AssertionError("add was given the caller, not the checkout")
    return add(store, edges.load_config(), document, here=here)


def _rm(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    here = values.here
    if here is not None and not isinstance(here, HereCaller | HereNotAProject):
        raise AssertionError("rm was given a checkout, not the caller")
    return rm(store, edges.load_config(), document, here=here)


def _list(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    here = values.here
    if here is not None and not isinstance(here, HereCaller | HereNotAProject):
        raise AssertionError("list was given a checkout, not the caller")
    return list_view(
        store,
        edges.load_config(),
        document,
        here=here,
        runs=values.runs,
        clock=edges.clock,
        local=edges.local,
    )


def _status(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return status(
        store,
        edges.load_config(),
        document,
        here=_caller(values),
        runs=_runs(values),
        clock=edges.clock,
        local=edges.local,
    )


def _inbox(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return inbox(store, document, here=_caller(values), clock=edges.clock)


def _send(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return send(
        store,
        edges.load_config(),
        document,
        here=_caller(values),
        clock=edges.clock,
        local=edges.local,
    )


def _reply(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return reply(
        store, edges.load_config(), document, here=_caller(values), clock=edges.clock
    )


def _cancel(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return cancel(
        store, edges.load_config(), document, here=_caller(values), clock=edges.clock
    )


def _changes(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return changes(store, document, here=_caller(values))


def _report_release(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return report_release_swept(
        store, edges.load_config(), document, here=_caller(values), clock=edges.clock
    )


@dataclass(frozen=True)
class ServedOperation:
    """What the door needs to know about one served operation: how to run it, what it
    needs gathered, and how its result document is read back."""

    run: _Runner
    #: The type the result document is read as; for ``list`` the request's subject
    #: decides, so ``result_for`` is used instead.
    result_type: type[ServedResult]
    #: Whether the operation reads ``config.yaml``; the hub loads it before the call
    #: scope, so a missing file is a refusal that costs no write lock.
    needs_config: bool = False
    #: What the client must gather for this ``document`` (D5).
    gathers: Callable[[object], Gather] = lambda document: NOTHING_GATHERED


#: The one registry: each served operation's name to its runner and result type.
#: To serve a new operation, add (1) its name to ``wire.protocol.SERVED_OPERATIONS``,
#: and to ``WRITING_CALLS`` and ``UNKNOWN_ADVICE`` there when it writes, and (2) an
#: entry here. ``tests/operations/test_served.py`` and ``tests/wire/test_protocol.py``
#: fail, naming what is missing, when they disagree.
SERVED: Final[dict[str, ServedOperation]] = {
    OperationName.DECISIONS: ServedOperation(_decisions, DecisionsResult),
    OperationName.MARK_READ: ServedOperation(_mark_read, MarkReadResult),
    OperationName.DISMISS: ServedOperation(_dismiss, DismissResult),
    OperationName.RETRACT: ServedOperation(_retract, RetractResult),
    OperationName.STANDING: ServedOperation(
        _standing, StandingResult, needs_config=True
    ),
    OperationName.WITHDRAW: ServedOperation(_withdraw, WithdrawResult),
    OperationName.ADD: ServedOperation(
        _add, SetUpResult, needs_config=True, gathers=_gather_add
    ),
    OperationName.RM: ServedOperation(
        _rm, SetUpResult, needs_config=True, gathers=_gather_rm
    ),
    OperationName.LIST: ServedOperation(
        _list, ListResult, needs_config=True, gathers=_gather_list
    ),
    OperationName.STATUS: ServedOperation(
        _status, StatusResult, needs_config=True, gathers=_gather_status
    ),
    OperationName.INBOX: ServedOperation(
        _inbox, InboxResult, gathers=_gather_caller_always
    ),
    OperationName.SEND: ServedOperation(
        _send, SendResult, needs_config=True, gathers=_gather_caller_always
    ),
    OperationName.REPLY: ServedOperation(
        _reply, ReplyResult, needs_config=True, gathers=_gather_caller_always
    ),
    OperationName.CANCEL: ServedOperation(
        _cancel, CancelResult, needs_config=True, gathers=_gather_caller_always
    ),
    OperationName.CHANGES: ServedOperation(
        _changes, ChangesResult, gathers=_gather_caller_always
    ),
    OperationName.REPORT_RELEASE: ServedOperation(
        _report_release,
        ReportReleaseResult,
        needs_config=True,
        gathers=_gather_caller_always,
    ),
}


def _served(name: str) -> ServedOperation:
    operation = SERVED.get(name)
    if operation is None:
        raise ValueError(f"{name} is not a served operation")
    return operation


def gather_needed(name: str, document: object) -> Gather:
    """What the client part must gather for the served operation ``name`` on
    ``document``: the placement and the hub both ask this, so they never differ."""
    return _served(name).gathers(document)


def client_values_from_body(
    name: str, document: object, body: Mapping[str, object]
) -> ClientValues:
    """The gathered values the call's body carries, parsed, for what ``name`` needs.

    A key the call does not need is ignored. A needed one that is missing or does not
    parse is a refusal, and nothing has run.

    Raises:
        CallRefused: ``malformed_call``: ``here`` or ``runs`` is missing, is not
            usable, or (for ``here``) holds an ``origin`` that is not in reduced form.
    """
    needed = gather_needed(name, document)
    here = (
        None
        if needed.here is None
        else parse_here(body.get(HERE_KEY), checkout=needed.here is HereKind.CHECKOUT)
    )
    runs = parse_runs(body.get(RUNS_KEY)) if needed.runs else None
    return ClientValues(here, runs)


def run_served(
    name: str,
    store: Store,
    document: object,
    edges: ServedEdges,
    values: ClientValues = ClientValues(),  # noqa: B008  frozen, no state to share
) -> ServedResult:
    """Run the served operation ``name`` on ``document``.

    Raises:
        ValueError: ``name`` is not a served operation.
        CallRefused: The operation is one the hub part refuses (``send`` with a wake
            due and ``edges.local`` ``None``).
    """
    return _served(name).run(store, document, edges, values)


def result_from_document(
    name: str, document: dict[str, object], request: object = None
) -> ServedResult:
    """The typed result of the served operation ``name``, rebuilt from its
    ``result_document`` form: the door's reply becomes the value the local way
    returns, so the CLI's renderers and exit codes need no second path.

    ``request`` is the document the call was made with, needed by ``list``, whose
    result type follows its subject.

    Raises:
        ValueError: ``name`` is not a served operation, or ``document`` is not that
            operation's result (pydantic's ``ValidationError`` is a ``ValueError``).
    """
    operation = _served(name)
    if name == OperationName.LIST:
        return _list_result(document, request)
    return TypeAdapter(operation.result_type).validate_python(document)


_LIST_VIEWS: Final[dict[ListSubject, type[ServedResult]]] = {
    ListSubject.PROGRAMS: ProgramsView,
    ListSubject.MEMBERS: MembersView,
    ListSubject.DEPENDENCIES: DependenciesView,
    ListSubject.STANDING: StandingView,
}


def _list_result(document: dict[str, object], request: object) -> ServedResult:
    parsed = ListRequest.model_validate(request)
    view = None if parsed.subject is None else _LIST_VIEWS[parsed.subject]
    if view is None:
        return ListResult.from_document(document)
    return TypeAdapter(view).validate_python(document)


def result_document(result: object) -> dict[str, object]:
    """``result`` as the JSON document both doors give: enums are strings."""
    if isinstance(result, ListResult):
        return result.document()
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if is_dataclass(result) and not isinstance(result, type):
        document: dict[str, object] = json.loads(json.dumps(asdict(result)))
        return document
    raise TypeError(f"not a result: {type(result).__name__}")
