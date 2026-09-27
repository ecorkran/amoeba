"""``amoeba submit``: the operator's and a bridge's way to write to the inbox.

Both levels derive from the inbox's own definitions, never the reverse:

- one subcommand per :class:`SubmissionKind` member, named from its value;
- one flag per field of that kind's payload model, named from the field.

So adding a kind — a member, a payload model, an effect — surfaces its
subcommand and its flags here with no second list to keep in step. A text or
enum field takes its flag as typed; every other field takes JSON. Pydantic
validates the result either way.

It calls :func:`amoeba.inbox.submit` and opens no store. It works whether or
not the resident process is running, and prints the submission id.
"""

from __future__ import annotations

import argparse
import json
from types import UnionType
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

from amoeba.inbox import submit
from amoeba.inbox.envelope import KIND_PAYLOAD_MODELS
from amoeba.store import SubmissionKind

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode

#: Prefix of the parsed-argument name each payload field is stored under, so a
#: field can never collide with ``--project``, ``--by``, or ``--id``.
_PAYLOAD_DEST_PREFIX = "payload_"


def subcommand_name(kind: SubmissionKind) -> str:
    """``create_project`` → ``create-project``."""
    return kind.value.replace("_", "-")


def _flag(field_name: str) -> str:
    """``blocked_state_id`` → ``--blocked-state-id``."""
    return "--" + field_name.replace("_", "-")


def _json_value(text: str) -> object:
    """An argparse type for a field that takes JSON. Pydantic checks the shape."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        # Specific: reported by argparse as a usage error, naming the flag.
        raise argparse.ArgumentTypeError(f"not valid JSON: {error}") from error


def _takes_text(annotation: object) -> bool:
    """Whether a payload field takes its flag as typed (else as JSON).

    Text and enum fields, and the optional form of either, take the flag as
    typed. Every other field takes JSON: ``--score 82.5``,
    ``--fallback-used null``, ``--findings '[...]'``.
    """
    members = (
        get_args(annotation)
        if get_origin(annotation) in (Union, UnionType)
        else (annotation,)
    )
    concrete = [member for member in members if member is not type(None)]
    return (
        len(concrete) == 1
        and isinstance(concrete[0], type)
        and issubclass(concrete[0], str)
    )


def add_submit_parser(subparsers: Any) -> None:
    """Add ``submit`` and one subcommand per submission kind.

    ``subparsers`` is typed ``Any`` for the same reason as in ``main.py``:
    argparse's subparsers-action type is private.
    """
    submit_parser = subparsers.add_parser(
        "submit",
        help="Drop a submission into the inbox.",
        description=(
            "Writes one submission durably and prints its id. Opens no store; "
            "works whether or not the process is running."
        ),
    )
    kinds = submit_parser.add_subparsers(dest="submission", required=True)

    for kind in SubmissionKind:
        kind_parser = kinds.add_parser(subcommand_name(kind))
        kind_parser.set_defaults(submission_kind=kind)
        kind_parser.add_argument("--project", required=True, help="The project.")
        kind_parser.add_argument(
            "--by", required=True, help="Who is submitting. Free-form."
        )
        kind_parser.add_argument(
            "--id",
            dest="submission_id",
            default=None,
            help="Reuse an id to retry safely. Generated when omitted.",
        )
        for name, field in KIND_PAYLOAD_MODELS[kind].model_fields.items():
            takes_text = _takes_text(field.annotation)
            kind_parser.add_argument(
                _flag(name),
                dest=_PAYLOAD_DEST_PREFIX + name,
                required=field.is_required(),
                type=str if takes_text else _json_value,
                metavar="VALUE" if takes_text else "JSON",
            )


def run_submit(args: argparse.Namespace) -> ExitCode:
    """Submit and print the id.

    Raises:
        InboxSubmitError: If the submission is invalid or cannot be written.
            Mapped to an exit code by the boundary handler.
    """
    from amoeba.cli.main import ExitCode

    kind: SubmissionKind = args.submission_kind
    payload = {
        name: getattr(args, _PAYLOAD_DEST_PREFIX + name)
        for name in KIND_PAYLOAD_MODELS[kind].model_fields
    }
    print(
        submit(
            project_id=args.project,
            kind=kind,
            payload=payload,
            submitted_by=args.by,
            submission_id=args.submission_id,
        )
    )
    return ExitCode.OK
