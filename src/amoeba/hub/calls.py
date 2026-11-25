"""One door call, handled as one transaction (slice 260, D6 to D9, D16).

``handle_call`` is a plain function the web app runs in a worker thread: no network
is needed to test it. It opens its own store connection, checks the token with a plain
read (a scanner never takes the write lock), then does everything else in one call
scope: touch the machine, expire kept results, return a kept result for a repeated
writing call, run the operation inside a savepoint, keep the result, commit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast

from amoeba.config.user_config import UserConfig
from amoeba.hub.call_refusals import CallReply, Refuser
from amoeba.hub.call_work import call_result, flagged, needs_config
from amoeba.operations.errors import OPERATION_ERRORS, CallRefused
from amoeba.operations.served import SERVED, ServedEdges
from amoeba.store.call_results import delete_expired, find_kept, keep
from amoeba.store.machines import (
    ActingMachine,
    hash_token,
    machine_for_token,
    machine_name,
    touch_machine,
)
from amoeba.store.store import Store, Transaction
from amoeba.wire.protocol import (
    BEARER_PREFIX,
    DOCUMENT_KEY,
    DONE_STATUS,
    HEADER_AUTHORIZATION,
    HEADER_CALL_ID,
    HEADER_CLIENT_VERSION,
    HEADER_DOOR_VERSION,
    HEADER_VALUE_MAX_LENGTH,
    HELLO_CALL,
    HELLO_MACHINE_KEY,
    MAX_CALL_BYTES,
    SERVED_OPERATIONS,
    STEP_CALLS,
    WRITING_CALLS,
    WRITING_STEPS,
    RefusalCode,
    done_reply,
    is_header_value,
)
from amoeba.wire.times import CALL_RESULT_LIFETIME_SECONDS, DOOR_VERSION


@dataclass(frozen=True)
class CallRequest:
    """One call as the web app received it."""

    name: str
    #: Header names as received; looked up case-insensitively.
    headers: Mapping[str, str]
    body: bytes
    #: The caller's address, for the refusal log line.
    peer: str


@dataclass(frozen=True)
class DoorHooks:
    """The fault seam of a call, like ``MoveHooks``. Production passes none.

    ``after_commit`` runs after the transaction committed and outside
    ``handle_call``'s promise never to raise: an exception it raises passes out, so
    the client gets no reply it accepts (D18).
    """

    after_commit: Callable[[], None] | None = None


@dataclass(frozen=True)
class _Checked:
    """What the checks that need no store found: a refusal to give once the touch is
    committed, or the call's parts."""

    refusal: tuple[RefusalCode, str] | None
    client_version: str | None
    call_id: str = ""
    document: object = None
    #: The whole body object: ``here`` and ``runs`` ride beside ``document`` (261 D5).
    body: Mapping[str, object] | None = None
    config: UserConfig | None = None


def _header(request: CallRequest, name: str) -> str | None:
    wanted = name.lower()
    return next((v for k, v in request.headers.items() if k.lower() == wanted), None)


def _token_hash(request: CallRequest) -> str | None:
    value = _header(request, HEADER_AUTHORIZATION)
    if value is None or not value.startswith(BEARER_PREFIX):
        return None
    token = value[len(BEARER_PREFIX) :].strip()
    return hash_token(token) if token else None


def _needs_config(name: str) -> bool:
    """Whether the step or served operation ``name`` reads ``config.yaml``."""
    operation = SERVED.get(name)
    return needs_config(name, operation is not None and operation.needs_config)


def _writes(name: str) -> bool:
    """Whether a call's result is kept for a repeat (D9; 262 D3)."""
    return name in WRITING_CALLS or name in WRITING_STEPS


def _is_acceptable(value: str | None) -> bool:
    return value is not None and is_header_value(value)


def _shown(value: str | None) -> str:
    """A client's header value as it may appear in a reply: quoted and cut short, so
    no control character reaches a log or a terminal."""
    return "no value" if value is None else repr(value[:HEADER_VALUE_MAX_LENGTH])


def _malformed(client_version: str | None, message: str) -> _Checked:
    return _Checked((RefusalCode.MALFORMED_CALL, message), client_version)


def _check_without_store(
    request: CallRequest, load_config: Callable[[], UserConfig]
) -> _Checked:
    """D8 step 2: the version, the headers, the body, the served list and the config.

    A failure is returned, not raised: the touch is committed first.
    """
    # What the client sent is stored and shown only when it passes the shared rule.
    sent_version = _header(request, HEADER_CLIENT_VERSION)
    client_version = sent_version if _is_acceptable(sent_version) else None
    version = _header(request, HEADER_DOOR_VERSION)
    if version != str(DOOR_VERSION):
        message = (
            f"the hub speaks door version {DOOR_VERSION}, this client sent "
            f"{_shown(version)}"
        )
        return _Checked((RefusalCode.DOOR_VERSION, message), client_version)
    call_id = _header(request, HEADER_CALL_ID)
    if call_id is None or client_version is None or not _is_acceptable(call_id):
        return _malformed(
            client_version,
            f"{HEADER_CALL_ID} and {HEADER_CLIENT_VERSION} are required, at most "
            f"{HEADER_VALUE_MAX_LENGTH} characters of letters, digits and . _ + ~ -",
        )
    if len(request.body) > MAX_CALL_BYTES:
        return _malformed(client_version, "the body is too large")
    try:
        body = json.loads(request.body)
    except ValueError:
        # Not JSON at all: the call is malformed and the reply says so.
        return _malformed(client_version, "the body is not JSON")
    if not isinstance(body, dict) or DOCUMENT_KEY not in body:
        return _malformed(client_version, f"the body needs a {DOCUMENT_KEY!r} key")
    fields = cast("dict[str, object]", body)
    document: object = fields[DOCUMENT_KEY]
    if request.name != HELLO_CALL and request.name not in (
        *SERVED_OPERATIONS,
        *STEP_CALLS,
    ):
        message = f"the door does not serve {request.name!r}"
        return _Checked((RefusalCode.NOT_SERVED, message), client_version)
    try:
        config = load_config() if _needs_config(request.name) else None
    except OPERATION_ERRORS as error:
        message = f"{type(error).__name__}: {error}"
        return _Checked((RefusalCode.HUB_ERROR, message), client_version)
    return _Checked(None, client_version, call_id, document, fields, config)


def _kept_reply(
    scope: Transaction,
    machine: ActingMachine,
    request: CallRequest,
    checked: _Checked,
    request_hash: str,
    refuser: Refuser,
    machine_label: str,
) -> CallReply | None:
    """A writing call's kept result for this id: its reply for a true repeat, a
    ``call_id_reused`` refusal for the same id on another call, ``None`` for none."""
    kept = find_kept(scope, machine.machine_id, checked.call_id)
    if kept is None:
        return None
    if kept.operation == request.name and kept.request_hash == request_hash:
        return CallReply(DONE_STATUS, kept.reply.encode("utf-8"))
    return refuser.refuse(
        RefusalCode.CALL_ID_REUSED,
        f"call id {checked.call_id} was used for another call",
        machine_label,
    )


def _operation_reply(  # noqa: PLR0913 - one call's parts
    store: Store,
    request: CallRequest,
    checked: _Checked,
    machine: ActingMachine,
    machine_label: str,
    request_hash: str,
    clock: Callable[[], datetime],
) -> bytes:
    """Run the operation and keep its result in one savepoint: a failure in either
    undoes both, so a result is never kept for an operation that did not apply."""
    store.act_as(machine)
    with store.write() as transaction:
        if request.name == HELLO_CALL:
            return done_reply({HELLO_MACHINE_KEY: machine_label})
        config = checked.config
        edges = ServedEdges(
            clock=clock,
            load_config=lambda: _loaded(config),
            local=None,
        )
        reply = done_reply(
            call_result(
                request.name, store, checked.document, checked.body or {}, edges
            )
        )
        if _writes(request.name):
            keep(
                transaction,
                machine.machine_id,
                checked.call_id,
                request.name,
                request_hash,
                reply.decode("utf-8"),
                clock(),
            )
        return reply


def _loaded(config: UserConfig | None) -> UserConfig:
    if config is None:
        raise AssertionError("an operation read a config the call did not load")
    return config


def _serve(
    store: Store,
    request: CallRequest,
    refuser: Refuser,
    clock: Callable[[], datetime],
    load_config: Callable[[], UserConfig],
) -> tuple[CallReply, bool]:
    """The reply, and whether a call scope committed (so ``after_commit`` runs)."""
    token_hash = _token_hash(request)
    if token_hash is None:
        return refuser.refuse(RefusalCode.BAD_TOKEN, _BAD_TOKEN), False
    with store.read() as reading:
        known = machine_for_token(reading, token_hash)
        label = None if known is None else machine_name(reading, known.machine_id)
    if known is None or label is None:
        return refuser.refuse(RefusalCode.BAD_TOKEN, _BAD_TOKEN), False
    checked = _check_without_store(request, load_config)
    request_hash = hashlib.sha256(request.body).hexdigest()
    with store.call_scope() as scope:
        machine = touch_machine(
            scope, token_hash, clock(), checked.client_version, None
        )
        if machine is None:
            # The token ended between the read and the scope (rm-machine, re-invite).
            return refuser.refuse(RefusalCode.BAD_TOKEN, _BAD_TOKEN), False
        # Every read after this acts as the caller, a kept result's work flag too.
        store.act_as(machine)
        if checked.refusal is not None:
            code, message = checked.refusal
            return refuser.refuse(code, message, label), True
        delete_expired(scope, clock(), CALL_RESULT_LIFETIME_SECONDS)
        if _writes(request.name):
            repeated = _kept_reply(
                scope, machine, request, checked, request_hash, refuser, label
            )
            if repeated is not None:
                return flagged(
                    repeated,
                    store,
                    machine.machine_id,
                    load_config,
                    clock(),
                    DOOR_VERSION,
                ), True
        try:
            body = _operation_reply(
                store, request, checked, machine, label, request_hash, clock
            )
        except CallRefused as refusal:
            # The hub part's own refusal (261 D12): the savepoint is already rolled
            # back, the touch commits with the scope, nothing is kept.
            return (
                refuser.refuse(RefusalCode(refusal.code), refusal.message, label),
                True,
            )
        except Exception as error:  # noqa: BLE001 - the hub's boundary for a call
            return refuser.for_exception(error, label), True
        reply = CallReply(DONE_STATUS, body)
        return flagged(
            reply, store, machine.machine_id, load_config, clock(), DOOR_VERSION
        ), True


_BAD_TOKEN: Final = (
    "this machine's token is not known to the hub; run `amoeba hub invite` there "
    "and `amoeba join` here"
)


def handle_call(
    request: CallRequest,
    *,
    open_store: Callable[[], Store],
    clock: Callable[[], datetime],
    load_config: Callable[[], UserConfig],
    hooks: DoorHooks = DoorHooks(),  # noqa: B008  frozen, no state to share
) -> CallReply:
    """Serve one call; never raises to the caller, apart from ``hooks.after_commit``.

    On an exception in the operation it rolls the operation's savepoint back, commits
    the touch, keeps nothing and refuses (``hub_error`` for the operations' own
    errors, ``hub_fault`` for anything else, with its traceback in the hub log). A
    failure before the scope, such as the store not opening, is refused the same way
    without the touch. Every refusal writes one log line.
    """
    refuser = Refuser(clock, request.peer)
    try:
        with open_store() as store:
            reply, committed = _serve(store, request, refuser, clock, load_config)
    except Exception as error:  # noqa: BLE001 - the hub's boundary for a call
        return refuser.for_exception(error, None)
    if committed and hooks.after_commit is not None:
        hooks.after_commit()
    return reply
