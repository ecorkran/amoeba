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
from typing import Final

from pydantic import BaseModel, TypeAdapter

from amoeba.operations.changes_models import ChangesResult
from amoeba.operations.decisions import DecisionsResult
from amoeba.operations.dismiss import DismissResult
from amoeba.operations.here_document import (
    HERE_KEY,
    parse_here,
)
from amoeba.operations.list_registry import (
    DependenciesView,
    MembersView,
    ProgramsView,
    StandingView,
)
from amoeba.operations.list_view import ListRequest, ListResult, ListSubject
from amoeba.operations.mark_read import MarkReadResult
from amoeba.operations.message_results import (
    CancelResult,
    InboxResult,
    ReplyResult,
    SendResult,
)
from amoeba.operations.names import OperationName
from amoeba.operations.report_release_models import ReportReleaseResult
from amoeba.operations.retract import RetractResult
from amoeba.operations.runs_document import RUNS_KEY, parse_runs
from amoeba.operations.served_runners import (
    Runner,
    gather_add,
    gather_caller_always,
    gather_list,
    gather_rm,
    gather_status,
    run_add,
    run_cancel,
    run_changes,
    run_decisions,
    run_dismiss,
    run_inbox,
    run_list,
    run_mark_read,
    run_reply,
    run_report_release,
    run_retract,
    run_rm,
    run_send,
    run_standing,
    run_status,
    run_withdraw,
)
from amoeba.operations.served_types import (
    NOTHING_GATHERED,
    ClientValues,
    Gather,
    HereKind,
    ServedEdges,
    ServedResult,
)
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.standing_models import StandingResult, WithdrawResult
from amoeba.operations.status import StatusResult
from amoeba.store.store import Store


@dataclass(frozen=True)
class ServedOperation:
    """What the door needs to know about one served operation: how to run it, what it
    needs gathered, and how its result document is read back."""

    run: Runner
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
    OperationName.DECISIONS: ServedOperation(run_decisions, DecisionsResult),
    OperationName.MARK_READ: ServedOperation(run_mark_read, MarkReadResult),
    OperationName.DISMISS: ServedOperation(run_dismiss, DismissResult),
    OperationName.RETRACT: ServedOperation(run_retract, RetractResult),
    OperationName.STANDING: ServedOperation(
        run_standing, StandingResult, needs_config=True
    ),
    OperationName.WITHDRAW: ServedOperation(run_withdraw, WithdrawResult),
    OperationName.ADD: ServedOperation(
        run_add, SetUpResult, needs_config=True, gathers=gather_add
    ),
    OperationName.RM: ServedOperation(
        run_rm, SetUpResult, needs_config=True, gathers=gather_rm
    ),
    OperationName.LIST: ServedOperation(
        run_list, ListResult, needs_config=True, gathers=gather_list
    ),
    OperationName.STATUS: ServedOperation(
        run_status, StatusResult, needs_config=True, gathers=gather_status
    ),
    OperationName.INBOX: ServedOperation(
        run_inbox, InboxResult, gathers=gather_caller_always
    ),
    OperationName.SEND: ServedOperation(
        run_send, SendResult, needs_config=True, gathers=gather_caller_always
    ),
    OperationName.REPLY: ServedOperation(
        run_reply, ReplyResult, needs_config=True, gathers=gather_caller_always
    ),
    OperationName.CANCEL: ServedOperation(
        run_cancel, CancelResult, needs_config=True, gathers=gather_caller_always
    ),
    OperationName.CHANGES: ServedOperation(
        run_changes, ChangesResult, gathers=gather_caller_always
    ),
    OperationName.REPORT_RELEASE: ServedOperation(
        run_report_release,
        ReportReleaseResult,
        needs_config=True,
        gathers=gather_caller_always,
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
