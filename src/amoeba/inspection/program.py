"""Rows for the program listings: ``program``, ``program-blocked`` and
``program-submissions``.

Supervisor-level: they read the program store and, for each member, that
member's own store, all **read-only**, so they work with the process stopped and
write nothing. With no program store each returns no rows. A program store at
the wrong schema version raises, as a project store does; so does any other
failure of the program store itself. A *member's* failure never raises: it is
reported as that member's row with its reason.

The member vocabulary is ``amoeba.program``'s (``read_member``), shared with the
Runner; this module adds only how the rows are laid out.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from amoeba.inspection import core
from amoeba.inspection.listing import Row
from amoeba.program import (
    MemberState,
    MemberUnreadableReason,
    Readable,
    Unreadable,
    member_state_in,
    read_member,
)
from amoeba.store import Member, Program, ProgramStore, Store, StoreError
from amoeba.store.paths import program_store_path, project_store_path

#: The ``blocked_on`` of a program-blocked row that is a member nobody can read.
#: Beside the store's ``BlockedKind`` values, which are a node's, not a member's.
MEMBER_UNREADABLE_BLOCKED_ON: Final = "member_unreadable"

#: What ``state`` says of a member that can be read.
READABLE_STATE: Final = "readable"

PROGRAM_COLUMNS: Final = (
    "program_id",
    "project_id",
    "requests_initiative",
    "consumed",
    "overrides",
    "concept_path",
    "state",
    "detail",
)
PROGRAM_BLOCKED_COLUMNS: Final = ("program_id", *core.BLOCKED_COLUMNS)
PROGRAM_SUBMISSION_COLUMNS: Final = (
    "id",
    "kind",
    "submitted_by",
    "submitted_at",
    "outcome",
    "reason",
)


def _open_program_store(supervisor_dir: Path) -> ProgramStore | None:
    """The program store, read-only; ``None`` when no program was ever registered."""
    path = program_store_path(supervisor_dir)
    if not path.exists():
        return None
    return ProgramStore.open_read_only(path)


def _members(
    supervisor_dir: Path,
) -> list[tuple[Program, Member]]:
    """Every program's members, programs and members in id order."""
    program_store = _open_program_store(supervisor_dir)
    if program_store is None:
        return []
    with program_store:
        return [
            (program, member)
            for program in program_store.programs()
            for member in program_store.members(program.program_id)
        ]


def program_rows(supervisor_dir: Path) -> list[Row]:
    """One row per member of every program, with its readability."""
    rows: list[Row] = []
    for program, member in _members(supervisor_dir):
        state = read_member(supervisor_dir, member)
        rows.append(
            {
                "program_id": program.program_id,
                "project_id": member.project_id,
                "requests_initiative": member.requests_initiative,
                "consumed": member.consumed.value,
                "overrides": ",".join(
                    f"{dependent}={mode.value}"
                    for dependent, mode in sorted(member.overrides.items())
                ),
                "concept_path": (
                    program.concept_path
                    if member.project_id == program.concept_member
                    else ""
                ),
                "state": (
                    READABLE_STATE
                    if isinstance(state, Readable)
                    else state.reason.value
                ),
                "detail": "" if isinstance(state, Readable) else state.detail,
            }
        )
    return rows


def program_submission_rows(supervisor_dir: Path) -> list[Row]:
    """Applied and rejected program submissions, in ``applied_seq`` order."""
    program_store = _open_program_store(supervisor_dir)
    if program_store is None:
        return []
    with program_store:
        return [
            {
                "id": record.id,
                "kind": record.kind.value,
                "submitted_by": record.submitted_by,
                "submitted_at": record.submitted_at.isoformat(),
                "outcome": record.outcome.value,
                "reason": record.reason or "",
                "payload": dict(record.payload),
            }
            for record in program_store.submissions()
        ]


def program_blocked_rows(supervisor_dir: Path) -> list[Row]:
    """Every member's blocked nodes, plus one row per member that cannot be read."""
    rows: list[Row] = []
    for program, member in _members(supervisor_dir):
        node_rows, state = _member_node_rows(supervisor_dir, member)
        rows.extend({"program_id": program.program_id, **row} for row in node_rows)
        if isinstance(state, Unreadable):
            rows.append(_unreadable_row(program.program_id, member, state))
    return rows


def _member_node_rows(
    supervisor_dir: Path, member: Member
) -> tuple[list[Row], MemberState]:
    """The member's blocked rows and its readability, from one read of its store.

    The store is opened once and both are read in one transaction, so a node row
    and an unreadable row cannot disagree. A store that is missing is
    ``read_member``'s to report (there is nothing to read twice).
    """
    path = project_store_path(supervisor_dir, member.project_id)
    if not path.is_file():
        return [], read_member(supervisor_dir, member)
    try:
        with Store.open_read_only(path) as store, store.read_transaction():
            return (
                core.project_blocked_rows(store, member.project_id),
                member_state_in(store, member),
            )
    except StoreError as error:
        # Specific: a member store that fails to open or read is that member's
        # problem, reported as its row; only the program store's own failures
        # may raise out of an inspection listing.
        return [], Unreadable(MemberUnreadableReason.STORE_UNREADABLE, str(error))


def _unreadable_row(program_id: str, member: Member, state: Unreadable) -> Row:
    """A ``member_unreadable`` row: the node columns are empty."""
    row: Row = dict.fromkeys(PROGRAM_BLOCKED_COLUMNS, "")
    row["program_id"] = program_id
    row["project_id"] = member.project_id
    row["blocked_on"] = MEMBER_UNREADABLE_BLOCKED_ON
    row["reason"] = f"{state.reason.value}: {state.detail}"
    return row
