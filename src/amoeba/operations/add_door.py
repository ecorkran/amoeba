"""What each door may set through ``add`` (slice 244, D1).

``wake_command`` is the PM's setting, made from the CLI: it lets Amoeba start a
program unattended. The MCP door does not take it, so no agent configures an
unattended start as a tool call. The published schema already omits it; this check
rejects a call that passes it anyway, the way any unknown field is rejected.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast

from amoeba.operations.set_up_models import (
    SetUpOutcome,
    SetUpProblem,
    SetUpProblemCode,
    SetUpResult,
)
from amoeba.store.vocabulary import Door

#: The doors that may set or clear a member's wake command.
WAKE_COMMAND_DOORS: Final = frozenset({Door.CLI})
WAKE_COMMAND_FIELD: Final = "wake_command"
_UNKNOWN_FIELD_TEXT: Final = "Extra inputs are not permitted"


def _mapping(value: object) -> Mapping[str, object] | None:
    """``value`` as a string-keyed mapping, or ``None`` if it is anything else."""
    if not isinstance(value, Mapping):
        return None
    # A JSON object always has string keys.
    return cast("Mapping[str, object]", value)


def _wake_command_locations(document: object) -> tuple[str, ...]:
    """Where ``wake_command`` appears in a raw ``add`` document: at the top, and in
    each member of ``bulk``. Anything that is not the expected shape is left to the
    operation's own validation."""
    top = _mapping(document)
    if top is None:
        return ()
    found: list[str] = []
    if WAKE_COMMAND_FIELD in top:
        found.append(WAKE_COMMAND_FIELD)
    bulk = _mapping(top.get("bulk"))
    members = None if bulk is None else bulk.get("members")
    if isinstance(members, list):
        for index, entry in enumerate(cast("list[object]", members)):
            member = _mapping(entry)
            if member is not None and WAKE_COMMAND_FIELD in member:
                found.append(f"bulk.members.{index}.{WAKE_COMMAND_FIELD}")
    return tuple(found)


def refuse_door_fields(document: object, door: Door) -> SetUpResult | None:
    """A ``rejected`` result naming each field ``door`` may not set, or ``None``."""
    if door in WAKE_COMMAND_DOORS:
        return None
    locations = _wake_command_locations(document)
    if not locations:
        return None
    return SetUpResult(
        outcome=SetUpOutcome.REJECTED,
        change_records=(),
        problems=tuple(
            SetUpProblem(
                code=SetUpProblemCode.MALFORMED,
                detail=f"{location}: {_UNKNOWN_FIELD_TEXT}",
            )
            for location in locations
        ),
        program=None,
        working_directory=None,
    )
