"""Why an operation rejected its request (slices 224 and 227).

One vocabulary for the read side (``status``, ``decisions``, ``mark_read``) and the
release side (``report_release``, ``changes``): each uses the codes that apply to it.
The CLI exits 1 for a rejected result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import ValidationError

from amoeba.store.models import Message
from amoeba.store.programs import list_programs
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import MessageKind


class RejectCode(StrEnum):
    """The closed set of rejection reasons."""

    UNKNOWN_PROGRAM = "unknown_program"
    MALFORMED = "malformed"
    BEYOND_LAST_RECORD = "beyond_last_record"
    #: The caller's directory is in no Context Forge project, or no program (227 D5).
    NOT_A_MEMBER = "not_a_member"
    #: ``correct`` or ``withdraw`` for a commit the member never reported (227 D2).
    NOT_REPORTED = "not_reported"
    #: ``send`` to a reference that is no active member (240 D3).
    UNKNOWN_RECIPIENT = "unknown_recipient"
    #: An explicit ``member`` names someone other than the member the directory is in.
    MEMBER_MISMATCH = "member_mismatch"
    #: ``send`` with an id that exists and carries different content (240 D2).
    ID_REUSED = "id_reused"
    #: ``send`` again of a request that is done, declined, cancelled or expired.
    REQUEST_ENDED = "request_ended"
    #: ``reply`` or ``cancel`` for an id no request has (240 D4).
    UNKNOWN_REQUEST = "unknown_request"
    #: ``reply`` by a member the request was not sent to.
    NOT_ADDRESSEE = "not_addressee"
    #: ``reply accept`` on a request that is already accepted; names the time.
    ALREADY_ACCEPTED = "already_accepted"
    #: A ``reply`` or ``cancel`` the request's current state does not allow.
    NOT_APPLICABLE = "not_applicable"
    #: ``send`` whose ``parent`` names no request (240 D8).
    PARENT_UNKNOWN = "parent_unknown"
    #: ``send`` whose parent is already ``max_chain_depth`` deep.
    CHAIN_TOO_DEEP = "chain_too_deep"
    #: ``send`` by a sender that already has the most requests, all still live.
    TOO_MANY_OPEN = "too_many_open"


def validation_problems(error: ValidationError) -> tuple[str, ...]:
    """One line per pydantic error: the field path, then the message."""
    return tuple(
        f"{'.'.join(str(part) for part in problem['loc']) or 'document'}: "
        f"{problem['msg']}"
        for problem in error.errors()
    )


def unknown_program_problem(transaction: Transaction, program: str) -> str | None:
    """A message listing the known ids when ``program`` is not one, else ``None``."""
    known = [entry.program_id for entry in list_programs(transaction)]
    if program in known:
        return None
    listed = ", ".join(known) if known else "none registered"
    return f"unknown program {program!r}; known programs: {listed}"


@dataclass(frozen=True)
class NotARequest:
    """Why an id names no request: ``detail`` goes into the rejection."""

    detail: str


def as_request(request_id: str, message: Message | None) -> Message | NotARequest:
    """``message`` when it is a request, else why ``request_id`` names none.

    A note's id is not a request's (243 D4): a note takes no reply, cannot be
    cancelled and cannot be a parent. A request always has a state (the table's
    ``CHECK``); a row that has none is a bug, and callers read ``effective_state``
    of what this returns without a second guard.

    Raises:
        ValueError: A request row has no state.
    """
    if message is None:
        return NotARequest(f"no request has the id {request_id!r}")
    if message.kind is MessageKind.NOTE:
        return NotARequest(
            f"{request_id!r} is a note, not a request: a note takes no reply, "
            "cannot be cancelled and cannot be a parent"
        )
    if message.state is None:
        raise ValueError(f"{request_id!r} is a request with no state")
    return message
