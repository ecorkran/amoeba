"""The text of requests and notes (slice 240, D7, D11, D12; slice 243).

Under each member in ``status`` and ``list``: **Requests** (age, state, and what a
request is "waiting on") and **Rejected calls** (the newest few), each left out when
empty. Both hold other agents' text, so the quoted-data notice is the first line of
whichever comes first. Requests are not things that wait on the PM: nothing here
changes ``Nothing needs you.``

And the text of the four message operations' results: a rejection prints
``rejected: <code>`` and a line per problem; anything else prints the notice first,
because request text follows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from amoeba.cli.render.text import (
    SEPARATOR,
    command_line,
    how_long,
    indented,
    prose_line,
    was_cut,
)
from amoeba.operations.message_results import (
    CancelResult,
    DeliveryView,
    InboxResult,
    NoteView,
    ReplyResult,
    RequestView,
    SendResult,
)
from amoeba.operations.names import OperationName
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.status_models import (
    MemberStatus,
    RejectedCall,
    RequestDirection,
    RequestEntry,
)

#: How many of a member's rejected calls the text shows; ``-j`` has them all.
REJECTED_CALLS_SHOWN: Final = 5
#: How deep ``inbox`` indents a note.
INBOX_NOTE_DEPTH: Final = 1
#: Where a note cut in the text is whole.
NOTE_CUT_IN_SEND: Final = "A note cut with … is whole in the -j result of this call."
INBOX_JSON_COMMAND: Final = f"amoeba {OperationName.INBOX.cli_name} -j"
_DIRECTION_WORD: Final = {
    RequestDirection.SENT: "to",
    RequestDirection.RECEIVED: "from",
}


def message_sections(members: list[MemberStatus], now: datetime) -> list[list[str]]:
    """The **Requests** and **Rejected calls** sections. The quoted-data notice is
    not here: ``render_waiting`` prints ``StatusResult.notice`` once, first."""
    return [
        section
        for section in (_requests(members, now), _rejected_calls(members))
        if section
    ]


def _requests(members: list[MemberStatus], now: datetime) -> list[str]:
    lines: list[str] = []
    for member in members:
        if not member.requests:
            continue
        lines.append(indented(member.member.name))
        for entry in member.requests:
            lines.extend(_request_lines(entry, now))
    return ["Requests", *lines] if lines else []


def _request_lines(entry: RequestEntry, now: datetime) -> list[str]:
    other = entry.other_name
    parts = (
        entry.id,
        f"{_DIRECTION_WORD[entry.direction]} {other}",
        entry.state.value,
        how_long(entry.created_at, now),
    )
    lines = [
        prose_line(indented("", 2), SEPARATOR.join(parts)),
        prose_line(indented("subject: ", 3), entry.subject),
    ]
    if entry.child_ids:
        lines.append(prose_line(indented("waiting on ", 3), ", ".join(entry.child_ids)))
    return lines


def _rejected_calls(members: list[MemberStatus]) -> list[str]:
    lines: list[str] = []
    for member in members:
        if not member.rejected_calls:
            continue
        lines.append(indented(member.member.name))
        for call in member.rejected_calls[:REJECTED_CALLS_SHOWN]:
            lines.extend(_rejected_call_lines(call))
        hidden = len(member.rejected_calls) - REJECTED_CALLS_SHOWN
        if hidden > 0:
            lines.append(indented(f"and {hidden} more (see -j)", 2))
    return ["Rejected calls", *lines] if lines else []


def _rejected_call_lines(call: RejectedCall) -> list[str]:
    when = call.created_at.strftime("%Y-%m-%d %H:%M")
    return [
        prose_line(indented("", 2), SEPARATOR.join((when, call.operation, call.code))),
        prose_line(indented("detail: ", 3), call.detail),
    ]


# --- the results of send, inbox, reply and cancel ----------------------------


def render_send(result: SendResult, *, now: datetime) -> str:
    """``sent <id>`` (or ``unchanged``), then the request or the note."""
    if result.note is not None:
        head = f"{result.outcome.value}: {result.note.id}"
        lines = [head, *_note_block(result.note, now)]
        if _note_was_cut(result.note, now):
            lines.append(NOTE_CUT_IN_SEND)
        return _with_notice(result.notice, lines)
    if result.request is None:
        return _rejection(result.rejection, result.problems)
    head = f"{result.outcome.value}: {result.request.id}"
    lines = [head, *_request_block(result.request, now)]
    if result.wake_problem is not None:
        lines.append(result.wake_problem)
    return _with_notice(result.notice, lines)


def render_reply(result: ReplyResult, *, now: datetime) -> str:
    """``<state>: <id>``, then the request."""
    if result.request is None:
        return _rejection(result.rejection, result.problems)
    head = f"{result.request.state.value}: {result.request.id}"
    return _with_notice(result.notice, [head, *_request_block(result.request, now)])


def render_cancel(result: CancelResult, *, now: datetime) -> str:
    """``cancelled: <id>``, then the request."""
    if result.request is None:
        return _rejection(result.rejection, result.problems)
    head = f"{result.outcome.value}: {result.request.id}"
    return _with_notice(result.notice, [head, *_request_block(result.request, now)])


def render_inbox(result: InboxResult, *, now: datetime) -> str:
    """The requests, the notes, the deliveries, then the number to pass as the next
    ``since``."""
    if result.as_of_seq is None:
        return _rejection(result.rejection, result.problems)
    lines: list[str] = []
    if result.requests:
        lines.append("Requests")
        for view in result.requests:
            lines.extend(_request_block(view, now, depth=1))
    if result.notes:
        lines.append("Notes")
        for note in result.notes:
            lines.extend(_note_block(note, now, depth=INBOX_NOTE_DEPTH))
        if any(_note_was_cut(note, now, INBOX_NOTE_DEPTH) for note in result.notes):
            lines.append(indented("A note cut with … is whole in:"))
            lines.append(command_line(INBOX_JSON_COMMAND))
    if result.deliveries:
        lines.append("Deliveries")
        lines.extend(_delivery_line(item) for item in result.deliveries)
    if not lines:
        lines.append("No requests." if result.since is None else "Nothing new.")
    lines.append(f"as_of_seq: {result.as_of_seq} (pass it as --since next time)")
    shows_text = bool(result.requests or result.notes)
    return _with_notice(result.notice if shows_text else None, lines)


def _rejection(code: RejectCode | None, problems: tuple[str, ...]) -> str:
    """``rejected: <code>: <problem>`` per problem.

    Raises:
        ValueError: The result has no code; every rejection has one.
    """
    if code is None:
        raise ValueError("a rejected result has a rejection code")
    head = f"rejected: {code.value}: "
    return "\n".join(prose_line(head, problem) for problem in problems) + "\n"


def _with_notice(notice: str | None, lines: list[str]) -> str:
    return "\n".join(([] if notice is None else [notice]) + lines) + "\n"


def _request_block(view: RequestView, now: datetime, depth: int = 0) -> list[str]:
    parts = [view.id]
    if view.direction is not None:
        other = (
            view.to_member
            if view.direction is RequestDirection.SENT
            else view.from_member
        )
        parts.append(f"{_DIRECTION_WORD[view.direction]} {other}")
    else:
        parts.append(f"{view.from_member} to {view.to_member}")
    parts += [view.state.value, how_long(view.created_at, now)]
    lines = [prose_line(indented("", depth + 1), SEPARATOR.join(parts))]
    details = (
        ("subject", view.subject),
        ("body", view.body),
        ("parent", view.parent_id),
        ("result", view.result),
        ("commit", view.result_commit),
        ("version", view.result_version),
        ("reason", view.reason),
    )
    lines.extend(
        prose_line(indented(f"{label}: ", depth + 2), value)
        for label, value in details
        if value
    )
    return lines


def _note_rows(view: NoteView, now: datetime, depth: int) -> list[tuple[str, str]]:
    """A note as ``(prefix, text)`` lines: its id, who it is from (and the program, for
    a program note) and its age, then its subject and body."""
    parts = [view.id, f"from {view.from_member}"]
    if view.to_program is not None:
        parts.append(f"to program {view.to_program}")
    parts.append(how_long(view.created_at, now))
    return [
        (indented("", depth + 1), SEPARATOR.join(parts)),
        (indented("subject: ", depth + 2), view.subject),
        (indented("body: ", depth + 2), view.body),
    ]


def _note_block(view: NoteView, now: datetime, depth: int = 0) -> list[str]:
    return [prose_line(prefix, text) for prefix, text in _note_rows(view, now, depth)]


def _note_was_cut(view: NoteView, now: datetime, depth: int = 0) -> bool:
    """Whether the text shows any line of ``view`` cut to the line width (a release
    note's body is several lines, shown on one)."""
    return any(was_cut(prefix, text) for prefix, text in _note_rows(view, now, depth))


def _delivery_line(item: DeliveryView) -> str:
    when = item.created_at.strftime("%Y-%m-%d %H:%M")
    parts = (str(item.seq), item.event.value, item.message_id, when)
    return prose_line(indented("", 1), SEPARATOR.join(parts))
