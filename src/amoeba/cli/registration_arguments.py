"""The flags of ``add``, ``rm`` and ``list`` and the requests they build (slice 229).

``add`` and ``rm`` flags map to request fields once, here: ``--rules P`` (repeatable)
is ``rules_paths: [P...]``; ``--default-rules`` is ``rules_default: true``;
``--no-rules`` is ``rules_paths: []``; ``--allow K`` is ``authorize_allow: [K...]``;
``--no-allow`` is ``authorize_allow: []``; ``--deny`` and ``--no-deny`` likewise. A
flag not given leaves its field omitted, which leaves the stored value alone.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any, Final

from amoeba.operations.list_view import ALL_NOT_ACCEPTED, SUBJECT_ALIASES, ListSubject
from amoeba.operations.names import OperationName
from amoeba.store.vocabulary import ConsumedMode

#: Splits ``MEMBER:PATH``, ``PROVIDER:CONSUMER`` and ``PROVIDER:MODE``.
SEPARATOR: Final = ":"

#: Every ``add`` flag and the value it has when it was not given.
_ADD_DEFAULTS: Final = {
    "program": None,
    "project": None,
    "rules": None,
    "default_rules": False,
    "no_rules": False,
    "allow": None,
    "no_allow": False,
    "deny": None,
    "no_deny": False,
    "depends_on": None,
    "concept": None,
}


def _split_once(text: str, flag: str, what: str) -> tuple[str, str]:
    """``LEFT:RIGHT`` split at the first ``:``; an empty side is a usage error."""
    left, separator, right = text.partition(SEPARATOR)
    if not (separator and left.strip() and right.strip()):
        raise argparse.ArgumentTypeError(f"{flag} takes {what}, got {text!r}")
    return left.strip(), right.strip()


def concept_argument(text: str) -> tuple[str, str]:
    return _split_once(text, "--concept", "MEMBER:PATH")


def depends_on_argument(text: str) -> tuple[str, str | None]:
    """``PROVIDER`` or ``PROVIDER:MODE`` with MODE one of the consumed modes."""
    provider, separator, mode = text.rpartition(SEPARATOR)
    if not separator:
        return text.strip(), None
    modes = [member.value for member in ConsumedMode]
    if not provider.strip() or mode not in modes:
        raise argparse.ArgumentTypeError(
            f"--depends-on takes PROVIDER or PROVIDER:MODE, MODE one of "
            f"{', '.join(modes)}; got {text!r}"
        )
    return provider.strip(), mode


def pair_argument(text: str) -> str:
    _split_once(text, "--pair", "PROVIDER:CONSUMER")
    return text


def register_add(
    commands: Any, json_parent: argparse.ArgumentParser
) -> argparse.ArgumentParser:
    parser = commands.add_parser(
        OperationName.ADD.cli_name,
        parents=[json_parent],
        help="register this repo (or --project) as a member of a program",
    )
    parser.set_defaults(operation=OperationName.ADD)
    parser.add_argument(
        "--program",
        metavar="ID",
        help="the program (default: the "
        "member's own, else one named for its Context Forge project)",
    )
    parser.add_argument(
        "--project",
        metavar="NAME",
        help="a Context Forge project name or id (default: the working directory's)",
    )
    rules = parser.add_mutually_exclusive_group()
    rules.add_argument(
        "--rules",
        action="append",
        metavar="PATH",
        help="rules file (repeatable); replaces the member's rules",
    )
    rules.add_argument(
        "--default-rules", action="store_true", help="read the config's default rules"
    )
    rules.add_argument("--no-rules", action="store_true", help="read no rules")
    for name in ("allow", "deny"):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            f"--{name}",
            action="append",
            metavar="KEY",
            help=f"authorize item to {name} (repeatable); replaces "
            f"the member's {name} list",
        )
        group.add_argument(
            f"--no-{name}", action="store_true", help=f"store an empty {name} list"
        )
    parser.add_argument(
        "--depends-on",
        action="append",
        type=depends_on_argument,
        metavar="PROVIDER[:MODE]",
        help="consume a provider (repeatable); MODE is from_source or from_release",
    )
    parser.add_argument(
        "--concept",
        type=concept_argument,
        metavar="MEMBER:PATH",
        help="set the program's concept",
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        help="register from a request "
        "document (YAML); - reads standard input; no other flag "
        "may be given",
    )
    return parser


def register_rm(
    commands: Any, json_parent: argparse.ArgumentParser
) -> argparse.ArgumentParser:
    parser = commands.add_parser(
        OperationName.RM.cli_name,
        aliases=["remove"],
        parents=[json_parent],
        help="remove members, dependency pairs or the concept (default: this repo)",
    )
    parser.set_defaults(operation=OperationName.RM)
    parser.add_argument(
        "members",
        nargs="*",
        metavar="MEMBER",
        help="Context Forge project names or ids",
    )
    parser.add_argument(
        "--pair",
        action="append",
        type=pair_argument,
        metavar="PROVIDER:CONSUMER",
        help="remove a dependency pair (repeatable)",
    )
    parser.add_argument(
        "--concept", action="store_true", help="clear the program's concept"
    )
    parser.add_argument("--program", metavar="ID", help="the program")
    return parser


def register_list(
    commands: Any, json_parent: argparse.ArgumentParser
) -> argparse.ArgumentParser:
    parser = commands.add_parser(
        OperationName.LIST.cli_name,
        parents=[json_parent],
        help="what needs you (default), or what is registered",
    )
    parser.set_defaults(operation=OperationName.LIST)
    subjects = [*(subject.value for subject in ListSubject), *SUBJECT_ALIASES]
    parser.add_argument(
        "subject",
        nargs="?",
        choices=subjects,
        metavar="SUBJECT",
        help=f"one of {', '.join(subjects)} (default: what needs you)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="also show what settled recently, or programs with no members",
    )
    parser.add_argument("--program", metavar="ID", help="only this program")
    return parser


def check_usage(parser: argparse.ArgumentParser, arguments: argparse.Namespace) -> None:
    """The combinations argparse cannot refuse by itself; exits 2 through ``parser``."""
    operation = getattr(arguments, "operation", None)
    if operation is OperationName.ADD and arguments.file is not None:
        others = [
            name
            for name, unset in _ADD_DEFAULTS.items()
            if getattr(arguments, name) != unset
        ]
        if others:
            flags = ", ".join("--" + name.replace("_", "-") for name in others)
            parser.error(f"--file cannot be combined with {flags}")
    if operation is OperationName.LIST and arguments.all and arguments.subject:
        subject = SUBJECT_ALIASES.get(arguments.subject) or ListSubject(
            arguments.subject
        )
        if subject in ALL_NOT_ACCEPTED:
            parser.error(f"--all does not apply to {arguments.subject}")


def add_document(
    arguments: argparse.Namespace, read_file: Callable[[str], object]
) -> dict[str, Any]:
    """The ``add`` request: the bulk document of ``--file``, or the given flags."""
    if arguments.file is not None:
        return {"bulk": read_file(arguments.file)}
    document: dict[str, Any] = {}
    for name in ("program", "project"):
        if getattr(arguments, name) is not None:
            document[name] = getattr(arguments, name)
    if arguments.rules is not None:
        document["rules_paths"] = list(arguments.rules)
    if arguments.default_rules:
        document["rules_default"] = True
    if arguments.no_rules:
        document["rules_paths"] = []
    for name in ("allow", "deny"):
        given = getattr(arguments, name)
        if given is not None:
            document[f"authorize_{name}"] = list(given)
        if getattr(arguments, f"no_{name}"):
            document[f"authorize_{name}"] = []
    if arguments.depends_on is not None:
        document["depends_on"] = [
            {"provider": provider} | ({} if mode is None else {"consumed": mode})
            for provider, mode in arguments.depends_on
        ]
    if arguments.concept is not None:
        member, path = arguments.concept
        document["concept"] = {"member": member, "path": path}
    return document


def rm_document(arguments: argparse.Namespace) -> dict[str, Any]:
    document: dict[str, Any] = {}
    if arguments.members:
        document["members"] = list(arguments.members)
    if arguments.pair is not None:
        document["pairs"] = list(arguments.pair)
    if arguments.concept:
        document["concept"] = True
    if arguments.program is not None:
        document["program"] = arguments.program
    return document


def list_document(arguments: argparse.Namespace) -> dict[str, Any]:
    document: dict[str, Any] = {}
    if arguments.subject is not None:
        document["subject"] = arguments.subject
    if arguments.all:
        document["all"] = True
    if arguments.program is not None:
        document["program"] = arguments.program
    return document
