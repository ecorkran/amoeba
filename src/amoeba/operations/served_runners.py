"""What each served operation runs and what each needs gathered (slice 261, D5, D12).

Each runner takes the store, the document, the edges and the client's parsed values and
returns the operation's result. This module imports nothing from ``operations.here``,
``naming``, ``run_gather`` or ``add_gather``: the hub runs it. Split from ``served``
to keep it under its size."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from amoeba.operations import list_view as list_view_module
from amoeba.operations import rm as rm_module
from amoeba.operations.add import AddRequest, add, names_no_member
from amoeba.operations.answer import record_answer
from amoeba.operations.cancel import cancel
from amoeba.operations.changes import changes
from amoeba.operations.decisions import decisions
from amoeba.operations.dismiss import dismiss
from amoeba.operations.here_document import (
    HereCaller,
    HereCheckout,
    HereNotAProject,
)
from amoeba.operations.inbox import inbox
from amoeba.operations.list_view import list_view
from amoeba.operations.mark_read import mark_read
from amoeba.operations.reply import reply
from amoeba.operations.report_release import report_release_swept
from amoeba.operations.retract import retract
from amoeba.operations.rm import rm
from amoeba.operations.runs_document import RunsDocument
from amoeba.operations.send import send
from amoeba.operations.served_types import (
    ANSWER_GATHER,
    CALLER_GATHER,
    NOTHING_GATHERED,
    SEND_GATHER,
    ClientValues,
    Gather,
    HereKind,
    ServedEdges,
    ServedResult,
)
from amoeba.operations.standing import standing
from amoeba.operations.status import status
from amoeba.operations.withdraw import withdraw
from amoeba.store.store import Store


def gather_caller_always(document: object) -> Gather:
    return CALLER_GATHER


def gather_status(document: object) -> Gather:
    return Gather(here=HereKind.CALLER, runs=True)


def gather_add(document: object) -> Gather:
    try:
        request = AddRequest.model_validate(document)
    except ValidationError:
        # Not a valid request: add rejects it as malformed, and needs no gather.
        return NOTHING_GATHERED
    return Gather(here=HereKind.CHECKOUT if names_no_member(request) else None)


def gather_rm(document: object) -> Gather:
    return CALLER_GATHER if rm_module.needs_here(document) else NOTHING_GATHERED


def gather_list(document: object) -> Gather:
    if not list_view_module.needs_here(document):
        return NOTHING_GATHERED
    return Gather(here=HereKind.CALLER, runs=True)


type Runner = Callable[[Store, object, ServedEdges, ClientValues], ServedResult]


def _caller(values: ClientValues) -> HereCaller | HereNotAProject:
    here = values.here
    if isinstance(here, HereCaller | HereNotAProject):
        return here
    raise AssertionError("the operation needs the gathered caller; none was parsed")


def _runs(values: ClientValues) -> RunsDocument:
    if values.runs is None:
        raise AssertionError("the operation needs the gathered runs; none was parsed")
    return values.runs


def run_decisions(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return decisions(store, document)


def run_mark_read(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return mark_read(store, document)


def run_dismiss(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return dismiss(store, document, clock=edges.clock)


def run_retract(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return retract(store, document, clock=edges.clock)


def run_standing(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return standing(
        store,
        document,
        max_chars=edges.load_config().passages_max_chars,
        now=edges.clock(),
    )


def run_withdraw(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return withdraw(store, document, now=edges.clock())


def run_add(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    here = values.here
    if here is not None and not isinstance(here, HereCheckout | HereNotAProject):
        raise AssertionError("add was given the caller, not the checkout")
    return add(store, edges.load_config(), document, here=here)


def run_rm(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    here = values.here
    if here is not None and not isinstance(here, HereCaller | HereNotAProject):
        raise AssertionError("rm was given a checkout, not the caller")
    return rm(store, edges.load_config(), document, here=here)


def run_list(
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
    )


def run_status(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return status(
        store,
        edges.load_config(),
        document,
        here=_caller(values),
        runs=_runs(values),
        clock=edges.clock,
    )


def run_inbox(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return inbox(store, document, here=_caller(values), clock=edges.clock)


def run_send(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return send(
        store,
        edges.load_config(),
        document,
        here=_caller(values),
        clock=edges.clock,
        logs_dir=_logs_dir(edges, values),
    )


def _logs_dir(edges: ServedEdges, values: ClientValues) -> Path:
    """The calling machine's logs directory: its own with no client file, the one the
    client sent through the door (262 D8)."""
    if edges.local is not None:
        return edges.local.logs_dir
    if values.logs_dir is None:
        raise AssertionError("send needs the gathered logs directory; none was parsed")
    return values.logs_dir


def gather_send(document: object) -> Gather:
    return SEND_GATHER


def gather_answer(document: object) -> Gather:
    return ANSWER_GATHER


def run_answer(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    """The hub part of ``answer`` (262 D7); the client part runs the resume."""
    if values.via is None:
        raise AssertionError("answer needs the door it came through; none was parsed")
    return record_answer(
        store, edges.load_config(), document, now=edges.clock(), via=values.via
    )


def run_reply(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return reply(
        store, edges.load_config(), document, here=_caller(values), clock=edges.clock
    )


def run_cancel(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return cancel(
        store, edges.load_config(), document, here=_caller(values), clock=edges.clock
    )


def run_changes(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return changes(store, document, here=_caller(values))


def run_report_release(
    store: Store, document: object, edges: ServedEdges, values: ClientValues
) -> ServedResult:
    return report_release_swept(
        store, edges.load_config(), document, here=_caller(values), clock=edges.clock
    )
