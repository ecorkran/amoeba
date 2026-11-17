"""``send`` of a note: the write transaction (slice 243, D1 to D3).

Called by ``send`` once the sender is resolved and, for a direct note, the recipient
too, so no ``cf`` call, process start or wait runs under the store lock. One write
transaction: sweep, check the id against an existing row (a retry is answered from it),
resolve a program's recipients, insert the note and one ``sent`` delivery each. A
rejection found here writes its ``message_rejections`` row in the same transaction.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.operations.message_models import SendOutcome, SendRequest
from amoeba.operations.message_results import SendResult
from amoeba.operations.note_room import make_room_for_note
from amoeba.operations.reject_codes import RejectCode, unknown_program_problem
from amoeba.operations.send_write import (
    SendProblem,
    id_reused,
    reject_send,
    same_content,
    sent_result,
)
from amoeba.store.message_sweep import sweep
from amoeba.store.messages import get_message
from amoeba.store.models import Message
from amoeba.store.notes import NewNote, insert_note
from amoeba.store.programs import members_of
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import MessageKind


def write_note(
    store: Store,
    config: UserConfig,
    *,
    sender: str,
    recipient: str | None,
    request: SendRequest,
    now: datetime,
) -> SendResult:
    """Store the note in ``request`` from ``sender``, or say why not.

    ``recipient`` is the resolved member of a direct note, ``None`` for a program note.

    Raises:
        StoreError: The store cannot be used.
    """
    with store.write() as transaction:
        sweep(transaction, now, config.prune_after_days)
        note = NewNote(
            message_id=request.id,
            from_member=sender,
            to_member=recipient,
            to_program=request.to_program,
            subject=request.subject,
            body=request.body,
        )
        existing = get_message(transaction, request.id)
        if existing is not None:
            return _resend(transaction, existing, note, request, now)
        recipients = _recipients(transaction, sender, recipient, request)
        if isinstance(recipients, SendProblem):
            return reject_send(transaction, sender, request, recipients, now)
        make_room_for_note(transaction, sender)
        stored = insert_note(transaction, note, recipients, now)
        return sent_result(SendOutcome.SENT, stored, now)


def _recipients(
    transaction: Transaction,
    sender: str,
    recipient: str | None,
    request: SendRequest,
) -> tuple[str, ...] | SendProblem:
    """Who gets the note. A direct note goes to its one member, the sender included
    when it names itself (D2). A program note goes to the program's active members
    except the sender, fixed now: a member added later gets nothing."""
    if recipient is not None:
        return (recipient,)
    program = request.to_program
    if program is None:
        raise AssertionError("a note has a recipient or a program; the model checked")
    unknown = unknown_program_problem(transaction, program)
    if unknown is not None:
        return SendProblem(RejectCode.UNKNOWN_RECIPIENT, unknown)
    others = tuple(
        member.project_id
        for member in members_of(transaction, program)
        if member.project_id != sender
    )
    if not others:
        return SendProblem(
            RejectCode.UNKNOWN_RECIPIENT,
            f"no one else in the program {program!r} to send a note to",
        )
    return others


def _resend(
    transaction: Transaction,
    existing: Message,
    note: NewNote,
    request: SendRequest,
    now: datetime,
) -> SendResult:
    """D3: the same id again. Same content is a retry; anything else is refused."""
    if not same_content(
        existing,
        kind=MessageKind.NOTE,
        from_member=note.from_member,
        to_member=note.to_member,
        to_program=note.to_program,
        parent_id=None,
        request=request,
    ):
        return reject_send(
            transaction, note.from_member, request, id_reused(request.id), now
        )
    return sent_result(SendOutcome.UNCHANGED, existing, now)
