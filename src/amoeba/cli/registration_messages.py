"""The flags of ``send``, ``inbox``, ``reply`` and ``cancel`` and the requests they
build (slice 240; ``--note`` and ``--to-program`` are slice 243).

No flag is ``required=True`` and no value is defaulted: a flag not given is left out of
the document, so the operation rejects it with the same detail on both doors (and the
rejection is recorded). ``--note`` is a flag that leaves ``kind`` out when absent, so
the document means a request. The one parse-time check is argparse's own: ``--body``
and ``--body-file`` exclude each other (exit 2).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

from amoeba.operations.message_models import ReplyAction
from amoeba.operations.names import OperationName
from amoeba.store.vocabulary import MessageKind

MEMBER_HELP = (
    "the sending member, when run from outside any member's checkout "
    "(a Context Forge project name or id)"
)


def _command(
    commands: Any, json_parent: argparse.ArgumentParser, name: OperationName, help: str
) -> argparse.ArgumentParser:
    parser = commands.add_parser(name.cli_name, parents=[json_parent], help=help)
    parser.set_defaults(operation=name)
    return parser


def _add_member(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--member", metavar="MEMBER", help=MEMBER_HELP)


def register_messages(commands: Any, json_parent: argparse.ArgumentParser) -> None:
    """``send``, ``inbox``, ``reply`` and ``cancel``."""
    send = _command(
        commands,
        json_parent,
        OperationName.SEND,
        "ask another repo for work, or send it or a program a note",
    )
    send.add_argument(
        "--note",
        dest="kind",
        action="store_const",
        const=MessageKind.NOTE.value,
        help="send information that needs no reply, not a request",
    )
    send.add_argument("--id", help="your id for the message; a retry reuses it")
    send.add_argument("--to", metavar="MEMBER", help="the addressee (name or id)")
    send.add_argument(
        "--to-program",
        metavar="ID",
        help="a note to every other member of this program (with --note)",
    )
    send.add_argument("--subject", help="what the request is about")
    body = send.add_mutually_exclusive_group()
    body.add_argument("--body", help="what you need, in full")
    body.add_argument(
        "--body-file",
        metavar="FILE",
        help="read the body from FILE, or from stdin when FILE is -",
    )
    send.add_argument("--parent", metavar="ID", help="the request this one serves")
    _add_member(send)
    inbox = _command(
        commands,
        json_parent,
        OperationName.INBOX,
        "the requests this repo sent and received, and what changed since a number",
    )
    inbox.add_argument(
        "--since",
        type=int,
        metavar="SEQ",
        help="the as_of_seq of an earlier call (default: every request still held)",
    )
    _add_member(inbox)
    reply = _command(
        commands,
        json_parent,
        OperationName.REPLY,
        "accept, decline or finish a request sent to this repo",
    )
    reply.add_argument("id", help="the request")
    reply.add_argument(
        "action",
        choices=[action.value for action in ReplyAction],
        help="what to do with it",
    )
    reply.add_argument("--text", help="the reason (decline) or the result (done)")
    reply.add_argument("--commit", help="done: the full hash of the commit")
    reply.add_argument("--version", help="done: the release tag")
    _add_member(reply)
    cancel = _command(
        commands,
        json_parent,
        OperationName.CANCEL,
        "end a request that is open or accepted, by its id",
    )
    cancel.add_argument("id", help="the request")
    cancel.add_argument("--reason", help="why it is cancelled")
    _add_member(cancel)


def _given(**values: object) -> dict[str, object]:
    """The values that were given: an absent flag stays out of the document."""
    return {key: value for key, value in values.items() if value is not None}


def send_document(
    arguments: argparse.Namespace, read_text: Callable[[str], str]
) -> dict[str, object]:
    """The ``send`` request; ``--body-file`` is read by ``read_text``."""
    body = (
        read_text(arguments.body_file)
        if arguments.body_file is not None
        else arguments.body
    )
    return _given(
        kind=arguments.kind,
        id=arguments.id,
        to=arguments.to,
        to_program=arguments.to_program,
        subject=arguments.subject,
        body=body,
        parent=arguments.parent,
        member=arguments.member,
    )


def inbox_document(arguments: argparse.Namespace) -> dict[str, object]:
    return _given(since=arguments.since, member=arguments.member)


def reply_document(arguments: argparse.Namespace) -> dict[str, object]:
    return _given(
        id=arguments.id,
        action=arguments.action,
        text=arguments.text,
        commit=arguments.commit,
        version=arguments.version,
        member=arguments.member,
    )


def cancel_document(arguments: argparse.Namespace) -> dict[str, object]:
    return _given(id=arguments.id, reason=arguments.reason, member=arguments.member)
