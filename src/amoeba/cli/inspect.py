"""``amoeba inspect``: read-only listings over store contents.

Every listing is declared in **one registry**, :data:`LISTINGS`. The registry is
the structural definition; the subcommand names derive from it, never the
reverse — a user-visible label is not logical structure. Slice 104 adds
``findings`` and ``verdicts`` by appending a :class:`Listing`, not by editing
this module's dispatch or the argument parser.

Every store is opened with :meth:`Store.open_read_only`, which never migrates,
never creates, and refuses writes. ``tests/test_writer_guard.py`` enforces
mechanically that this module never reaches for the read-write open.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from amoeba.cli import inspect_evidence, inspect_inbox
from amoeba.process.supervisor import discover_project_ids, store_path_for
from amoeba.store import Channel, Store, paths

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode

#: One row of a listing: ordered column name/value pairs, so the table and the
#: JSON forms cannot disagree about either content or order.
type Row = dict[str, object]


@dataclass(frozen=True)
class ChoiceOption:
    """An optional flag taking one value from a closed set, e.g. ``--channel``."""

    flag: str
    help_text: str
    choices: tuple[str, ...]


@dataclass(frozen=True)
class ValueOption:
    """An optional flag taking one free value, e.g. ``--node ID``."""

    flag: str
    help_text: str
    metavar: str


@dataclass(frozen=True)
class Listing:
    """One inspection listing: its name, its query, and its columns.

    Exactly one of ``rows`` and ``supervisor_rows`` is set. Which one is what
    makes a listing project-scoped or supervisor-level — never its name.

    Attributes:
        name: The subcommand name. Derived *from* this registry entry.
        help_text: One line, shown by ``--help``.
        columns: Column order for the table form.
        rows: For a project-scoped listing: receives an open **read-only**
            store and the parsed arguments.
        supervisor_rows: For a supervisor-level listing: receives the
            supervisor directory, and opens no store.
        flags: Extra boolean flags, as ``(flag, help)`` pairs.
        choice_options: Extra optional flags taking one value from a set.
        value_options: Extra optional flags taking one free value.
    """

    name: str
    help_text: str
    columns: tuple[str, ...]
    rows: Callable[[Store, argparse.Namespace], list[Row]] | None = None
    supervisor_rows: Callable[[Path], list[Row]] | None = None
    flags: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    choice_options: tuple[ChoiceOption, ...] = field(default_factory=tuple)
    value_options: tuple[ValueOption, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if (self.rows is None) == (self.supervisor_rows is None):
            raise ValueError(
                f"listing {self.name!r} must set exactly one of rows and "
                "supervisor_rows"
            )

    @property
    def requires_project(self) -> bool:
        """Whether ``--project`` is required: every project-scoped listing."""
        return self.supervisor_rows is None


def _node_rows(store: Store, args: argparse.Namespace) -> list[Row]:
    """Every node in a project."""
    return [
        {
            "id": node.id,
            "kind": node.kind.value,
            "status": node.status.value,
            "title": node.title,
            "parent_id": node.parent_id or "",
        }
        for node in store.nodes_for_project(args.project)
    ]


def _blocked_rows(store: Store, args: argparse.Namespace) -> list[Row]:
    """Every blocked node, with what it is blocked on."""
    return [
        {
            "node_id": blocked.node.id,
            "title": blocked.node.title,
            "blocked_on": blocked.blocked_state.kind.value,
            "context": blocked.blocked_state.context,
        }
        for blocked in store.blocked(args.project)
    ]


def _journal_rows(store: Store, args: argparse.Namespace) -> list[Row]:
    """Journal entries for a project, optionally only the unresolved ones."""
    entries = store.journal_entries(args.project, include_resolved=not args.unresolved)
    return [
        {
            "id": entry.id,
            "node_id": entry.node_id,
            "kind": entry.kind.value,
            "outcome": entry.outcome.value if entry.outcome else "",
            "resolved_by": entry.resolved_by.value if entry.resolved_by else "",
            "issued_at": entry.issued_at.isoformat() if entry.issued_at else "",
            "parameters": entry.parameters,
            "result": entry.result if entry.result is not None else {},
        }
        for entry in entries
    ]


def _project_rows(supervisor_dir: Path) -> list[Row]:
    """Project ids with a store in the supervisor directory.

    An empty supervisor directory yields an empty list rather than failing: a
    supervisor that has never run is a valid state.
    """
    return [
        {
            "project_id": project_id,
            "store": str(store_path_for(supervisor_dir, project_id)),
        }
        for project_id in discover_project_ids(supervisor_dir)
    ]


#: The name of the ``projects`` listing, which tests refer to.
PROJECTS_LISTING = "projects"

_NODE_OPTION = ValueOption(flag="--node", help_text="Only this node.", metavar="ID")

#: The listing registry — the single structural definition of what ``inspect``
#: can show. Adding a listing is appending here; nothing else changes.
LISTINGS: tuple[Listing, ...] = (
    Listing(
        name=PROJECTS_LISTING,
        help_text="Project ids that have a store in the supervisor directory.",
        columns=("project_id", "store"),
        supervisor_rows=_project_rows,
    ),
    Listing(
        name="inbox",
        help_text="Inbox files that are pending, quarantined, or failed.",
        columns=("state", "file", "attempts", "reason", "problem"),
        supervisor_rows=inspect_inbox.inbox_rows,
    ),
    Listing(
        name="nodes",
        help_text="Lifecycle nodes for a project.",
        columns=("id", "kind", "status", "title", "parent_id"),
        rows=_node_rows,
    ),
    Listing(
        name="blocked",
        help_text="Blocked nodes for a project, and what each is blocked on.",
        columns=("node_id", "title", "blocked_on", "context"),
        rows=_blocked_rows,
    ),
    Listing(
        name="journal",
        help_text="Command journal entries for a project.",
        columns=(
            "id",
            "node_id",
            "kind",
            "outcome",
            "resolved_by",
            "issued_at",
        ),
        rows=_journal_rows,
        flags=(("--unresolved", "Only entries still in flight."),),
    ),
    Listing(
        name="submissions",
        help_text="Applied and rejected inbox submissions for a project.",
        columns=(
            "applied_seq",
            "id",
            "kind",
            "outcome",
            "reason",
            "submitted_by",
            "submitted_at",
        ),
        rows=inspect_inbox.submission_rows,
    ),
    Listing(
        name="messages",
        help_text="Intent and escalation messages for a project, in seq order.",
        columns=(
            "seq",
            "id",
            "channel",
            "node_id",
            "blocked_state_id",
            "submission_id",
            "journal_entry_id",
            "acknowledged_at",
        ),
        rows=inspect_inbox.message_rows,
        choice_options=(
            ChoiceOption(
                flag="--channel",
                help_text="Only this channel. Every channel when omitted.",
                choices=tuple(channel.value for channel in Channel),
            ),
        ),
    ),
    Listing(
        name="verdicts",
        help_text="Recorded review verdicts for a project, in arrival order.",
        columns=inspect_evidence.VERDICT_COLUMNS,
        rows=inspect_evidence.verdict_rows,
        value_options=(_NODE_OPTION,),
    ),
    Listing(
        name="findings",
        help_text="Findings by content key, or one review's changes (--verdict).",
        columns=inspect_evidence.FINDING_COLUMNS,
        rows=inspect_evidence.finding_rows,
        value_options=(
            _NODE_OPTION,
            ValueOption(
                flag="--verdict",
                help_text="Show this review's findings as new, recurring, gone.",
                metavar="ID",
            ),
        ),
    ),
)

#: By name, so dispatch is a lookup rather than a chain of comparisons.
LISTINGS_BY_NAME: dict[str, Listing] = {listing.name: listing for listing in LISTINGS}


def run_listing(name: str, args: argparse.Namespace, *, use_json: bool) -> ExitCode:
    """Run one listing and print it.

    Raises:
        StoreError: If the project's store cannot be opened read-only — which
            includes a store needing migration, since inspection never
            migrates. Mapped to an exit code by the boundary handler.
    """
    from amoeba.cli.main import ExitCode

    listing = LISTINGS_BY_NAME[name]
    supervisor_dir = paths.store_dir()

    if listing.supervisor_rows is not None:
        rows = listing.supervisor_rows(supervisor_dir)
    elif listing.rows is not None:
        project_store_file = store_path_for(supervisor_dir, args.project)
        with Store.open_read_only(project_store_file) as store:
            rows = listing.rows(store, args)
    else:
        raise ValueError(f"listing {name!r} declares no rows")

    if use_json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        _print_table(listing.columns, rows)

    return ExitCode.OK


def _print_table(columns: Sequence[str], rows: Sequence[Row]) -> None:
    """Print rows as an aligned table, or a clear note when there are none."""
    if not rows:
        print("(none)")
        return

    widths = {
        column: max(len(column), *(len(_cell(row, column)) for row in rows))
        for column in columns
    }
    print("  ".join(column.ljust(widths[column]) for column in columns))
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(_cell(row, column).ljust(widths[column]) for column in columns))


def _cell(row: Row, column: str) -> str:
    """Render one cell. Mappings are compacted so a row stays one line."""
    value = row.get(column, "")
    if isinstance(value, dict):
        return json.dumps(value, default=str, separators=(",", ":"))
    return str(value)
