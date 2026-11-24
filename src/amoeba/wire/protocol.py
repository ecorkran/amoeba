"""The call and reply shapes of the door (slice 260, D6, D9, D10, D11).

Everything the client and the hub must agree on beyond the times: the served
operation names, the refusal codes and their HTTP statuses, the headers, the reply
bodies, and the advice a client gives when a writing call's outcome is unknown.
The served names are plain strings; a test asserts each is an ``OperationName``
value, because this package imports nothing from the rest of ``amoeba``.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

#: The operations the door serves, in one place. Later slices add names here.
SERVED_OPERATIONS: Final[tuple[str, ...]] = (
    "decisions",
    "mark_read",
    "dismiss",
    "retract",
    "standing",
    "withdraw",
    "add",
    "rm",
    "list",
    "status",
    "inbox",
    "reply",
    "cancel",
    "changes",
    "report_release",
    "send",
    "answer",
)
#: Served operations that write, so their results are kept for a repeated call (D9).
#: ``inbox`` and ``changes`` read. ``list`` and ``status`` write only the message
#: expiry, which is safe to run twice, so they keep no result (261 D12).
WRITING_CALLS: Final[frozenset[str]] = frozenset(
    {
        "mark_read",
        "dismiss",
        "retract",
        "standing",
        "withdraw",
        "add",
        "rm",
        "reply",
        "cancel",
        "report_release",
        "send",
        "answer",
    }
)
#: The steps (262 D3, D4): the hub side of each store transaction a client-run
#: command makes. Not operations a person calls, so apart from the served list. A test
#: asserts they equal the names in ``operations.steps.models.STEP_MODELS``.
STEP_CALLS: Final[tuple[str, ...]] = (
    "pause_begin",
    "pause_sources",
    "question_insert",
    "question_hold",
    "question_claim_held",
    "question_replace_claim",
    "question_wait",
    "question_settle",
    "resume_claim",
    "resume_read",
    "resume_record",
    "claim_work",
    "open_runs",
    "wake_read",
    "wake_set_pid",
    "wake_finish",
)
#: The steps whose result is kept for a repeated call: the writing rows of
#: ``STEP_MODELS``.
WRITING_STEPS: Final[frozenset[str]] = frozenset(
    {
        "pause_begin",
        "question_insert",
        "question_hold",
        "question_claim_held",
        "question_replace_claim",
        "question_wait",
        "question_settle",
        "resume_claim",
        "resume_record",
        "claim_work",
        "wake_set_pid",
        "wake_finish",
    }
)
#: The door's own call: a token check that returns the machine's name. Not an operation.
HELLO_CALL: Final = "hello"
#: The key of ``hello``'s result document.
HELLO_MACHINE_KEY: Final = "machine"

#: The request body key holding the operation's document.
DOCUMENT_KEY: Final = "document"
#: The body keys beside it for values only the client can read (261 D5): the caller's
#: project (or, for ``add``, its checkout) and the machine's runs. A call that does not
#: need one sends none and the hub ignores one it is sent.
HERE_BODY_KEY: Final = "here"
RUNS_BODY_KEY: Final = "runs"
#: ``answer``'s door as the client states it (262 D7), and ``send``'s calling machine's
#: logs directory, under which a claimed wake's logs go (262 D8).
VIA_BODY_KEY: Final = "via"
LOGS_DIR_BODY_KEY: Final = "logs_dir"
#: A body over this, or with no valid length, is refused before it is read.
MAX_CALL_BYTES: Final = 1024 * 1024

HEADER_AUTHORIZATION: Final = "Authorization"
HEADER_DOOR_VERSION: Final = "Amoeba-Door-Version"
HEADER_CLIENT_VERSION: Final = "Amoeba-Client-Version"
HEADER_CALL_ID: Final = "Amoeba-Call-Id"
BEARER_PREFIX: Final = "Bearer "
#: The URL path of a call is ``CALL_PATH_PREFIX + <name>``.
CALL_PATH_PREFIX: Final = "/call/"


class RefusalCode(StrEnum):
    """Why the hub did not run an operation (D6)."""

    BAD_TOKEN = "bad_token"
    DOOR_VERSION = "door_version"
    MALFORMED_CALL = "malformed_call"
    NOT_SERVED = "not_served"
    CALL_ID_REUSED = "call_id_reused"
    HUB_ERROR = "hub_error"
    HUB_FAULT = "hub_fault"


#: The HTTP status each refusal travels with. The client goes by the body, not this.
REFUSAL_STATUS: Final[dict[RefusalCode, int]] = {
    RefusalCode.BAD_TOKEN: 401,
    RefusalCode.DOOR_VERSION: 426,
    RefusalCode.MALFORMED_CALL: 400,
    RefusalCode.NOT_SERVED: 404,
    RefusalCode.CALL_ID_REUSED: 409,
    RefusalCode.HUB_ERROR: 500,
    RefusalCode.HUB_FAULT: 500,
}
#: The status of a done reply.
DONE_STATUS: Final = 200

OUTCOME_DONE: Final = "done"
OUTCOME_REFUSED: Final = "refused"

#: Keys a done reply's result document carries beside the result (262 D10): whether
#: the calling machine has work waiting, or why the hub could not tell. The client takes
#: them out before it rebuilds the result.
WORK_REPLY_KEY: Final = "work"
WORK_PROBLEM_REPLY_KEY: Final = "work_problem"


class DoneReply(BaseModel):
    """The hub ran the operation; ``result`` is its result document."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["done"]
    result: dict[str, object]


class RefusedReply(BaseModel):
    """The hub did not run the operation."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["refused"]
    code: RefusalCode
    message: str


Reply = DoneReply | RefusedReply
_REPLY_ADAPTER: Final[TypeAdapter[Reply]] = TypeAdapter(
    Reply  # pyright: ignore[reportArgumentType]
)


def done_reply(result: dict[str, object]) -> bytes:
    """A done reply body."""
    return (
        DoneReply(outcome=OUTCOME_DONE, result=result).model_dump_json().encode("utf-8")
    )


def refused_reply(code: RefusalCode, message: str) -> bytes:
    """A refused reply body."""
    return (
        RefusedReply(outcome=OUTCOME_REFUSED, code=code, message=message)
        .model_dump_json()
        .encode("utf-8")
    )


def parse_reply(body: bytes) -> Reply | None:
    """The reply a body holds, or ``None`` when it is not a reply (D6).

    Anything that is not a done or refused reply counts as no reply: the status is
    never read, so a proxy's error page cannot be taken for an answer.
    """
    try:
        return _REPLY_ADAPTER.validate_json(body)
    except ValidationError:
        return None


#: What to tell the caller when a writing call's outcome is unknown, per operation
#: (D10). Running the call again is itself the read: each answers ``unchanged`` when
#: the store is already in the state it asks for.
_OPERATION_ADVICE: Final[dict[str, str]] = {
    "mark_read": "Run it again; `unchanged` means the marker is already there.",
    "retract": "Run it again; `unchanged` means the answer is already retracted.",
    "dismiss": (
        "Run it again; `unchanged` means the question is already closed, and "
        "`closed_reason` in the result says how."
    ),
    "standing": (
        "Run it again with the same text; `unchanged` with an id means that "
        "standing answer exists."
    ),
    "withdraw": "Run it again; `unchanged` means it is already withdrawn.",
    "send": (
        "Run `amoeba inbox` or `amoeba list` and look for the request before "
        "sending again."
    ),
    "reply": (
        "Run `amoeba inbox` or `amoeba list` and look for the request before "
        "replying again."
    ),
    "cancel": (
        "Run `amoeba inbox` or `amoeba list` and look for the request before "
        "cancelling again."
    ),
    "add": "Run `amoeba list members` and look for the member and its checkout.",
    "rm": "Run `amoeba list members` and look for the member and its checkout.",
    "report_release": (
        "Run it again. A report that was applied answers `unchanged` and a "
        "withdrawal that was applied is rejected because nothing is stored; "
        "neither writes. A correction that was applied is applied again with the "
        "same text."
    ),
    "answer": ("Run `amoeba list` and look at the question before answering again."),
}
#: The one advice for every writing step (262 D11): the command stopped there, and the
#: store says what happens next.
STEP_ADVICE: Final = (
    "The command stopped at this step; the next call from this machine starts the "
    "work again from what the store holds."
)
UNKNOWN_ADVICE: Final[dict[str, str]] = {
    **_OPERATION_ADVICE,
    **dict.fromkeys(WRITING_STEPS, STEP_ADVICE),
}

#: A machine's name (D3): lower-case letters and digits, with ``.``, ``_`` and ``-``.
MACHINE_NAME_PATTERN: Final = r"[a-z0-9][a-z0-9._-]*"
MACHINE_NAME_MAX_LENGTH: Final = 64
_MACHINE_NAME: Final = re.compile(MACHINE_NAME_PATTERN)


def is_machine_name(text: str) -> bool:
    """Whether ``text`` is a valid machine name."""
    return (
        len(text) <= MACHINE_NAME_MAX_LENGTH
        and _MACHINE_NAME.fullmatch(text) is not None
    )


#: A header value a client supplies and the hub stores or shows (the call id and the
#: client version): letters and digits with ``.``, ``_``, ``+``, ``~`` and ``-``,
#: no space or control character, so it is safe in a store, a log line and a terminal.
HEADER_VALUE_PATTERN: Final = r"[A-Za-z0-9][A-Za-z0-9._+~-]*"
HEADER_VALUE_MAX_LENGTH: Final = 64
_HEADER_VALUE: Final = re.compile(HEADER_VALUE_PATTERN)


def is_header_value(text: str) -> bool:
    """Whether ``text`` is an acceptable call id or client version."""
    return (
        len(text) <= HEADER_VALUE_MAX_LENGTH
        and _HEADER_VALUE.fullmatch(text) is not None
    )
