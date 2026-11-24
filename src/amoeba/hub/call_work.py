"""A step's or a served operation's result, and the work flag in every done reply
(slice 262, D3, D10).

A step runs ``run_step`` inside the call scope; its document not fitting its request
model is ``malformed_call``.

After the call's own work, inside its call scope, the hub asks ``work_waiting`` for
the calling machine and puts ``work: true`` or ``work: false`` in the done reply's
result document. A kept result is stored without the flag and gets a fresh one each
time it is returned. When the hub's ``config.yaml`` cannot load, the flag cannot be
worked out: the reply carries ``work_problem`` with the error's text and no ``work``,
never a false flag. Refused replies carry neither.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.hub.call_refusals import CallReply
from amoeba.operations.errors import MALFORMED_CALL, OPERATION_ERRORS, CallRefused
from amoeba.operations.served import (
    ServedEdges,
    client_values_from_body,
    result_document,
    run_served,
)
from amoeba.operations.steps.dispatch import StepDocumentError, StepEdges, run_step
from amoeba.operations.steps.models import STEP_MODELS
from amoeba.operations.steps.work import work_waiting
from amoeba.store.store import Store
from amoeba.wire.protocol import (
    DONE_STATUS,
    STEP_CALLS,
    WORK_PROBLEM_REPLY_KEY,
    WORK_REPLY_KEY,
    DoneReply,
    done_reply,
)


def call_result(
    name: str,
    store: Store,
    document: object,
    body: Mapping[str, object],
    edges: ServedEdges,
) -> dict[str, object]:
    """The result document of the step or served operation ``name``.

    Raises:
        CallRefused: ``malformed_call`` for a step document that does not fit, or the
            served operation's own refusal.
    """
    if name in STEP_CALLS:
        try:
            reply = run_step(
                name, store, document, StepEdges(edges.clock, edges.load_config)
            )
        except StepDocumentError as error:
            raise CallRefused(MALFORMED_CALL, str(error)) from error
        return reply.model_dump(mode="json")
    values = client_values_from_body(name, document, body)
    return result_document(run_served(name, store, document, edges, values))


def needs_config(name: str, served_needs_config: bool) -> bool:
    """Whether the call ``name`` reads ``config.yaml``: a step's ``STEP_MODELS`` row,
    or the served operation's own flag."""
    step = STEP_MODELS.get(name)
    return served_needs_config if step is None else step.needs_config


def work_keys(
    store: Store,
    machine_id: int,
    load_config: Callable[[], UserConfig],
    now: datetime,
) -> dict[str, object]:
    """``work`` for ``machine_id``, or ``work_problem`` when the config cannot load.

    Runs in its own read, a savepoint inside the call scope.
    """
    try:
        config = load_config()
    except OPERATION_ERRORS as error:
        # Not raised: the call's own work is done and needs no config, so it stands.
        # The client prints this text in place of a flag (D10).
        return {WORK_PROBLEM_REPLY_KEY: f"{type(error).__name__}: {error}"}
    with store.read() as transaction:
        waiting = work_waiting(transaction, machine_id, config, now)
    return {WORK_REPLY_KEY: waiting}


def with_work(reply: bytes, keys: dict[str, object]) -> bytes:
    """The done reply ``reply`` with ``keys`` added to its result document."""
    parsed = DoneReply.model_validate_json(reply)
    return done_reply({**parsed.result, **keys})


def flagged(
    reply: CallReply,
    store: Store,
    machine_id: int,
    load_config: Callable[[], UserConfig],
    now: datetime,
) -> CallReply:
    """A done reply with the calling machine's work flag, fresh on every return; a
    refusal unchanged. Called inside the call scope, after the call's own work."""
    if reply.status != DONE_STATUS:
        return reply
    keys = work_keys(store, machine_id, load_config, now)
    return CallReply(reply.status, with_work(reply.body, keys))
