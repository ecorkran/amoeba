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
from typing import TYPE_CHECKING

from amoeba.process.supervisor import discover_project_ids, store_path_for
from amoeba.store import Store, paths

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode

#: One row of a listing: ordered column name/value pairs, so the table and the
#: JSON forms cannot disagree about either content or order.
type Row = dict[str, object]


@dataclass(frozen=True)
class Listing:
    """One inspection listing: its name, its query, and its columns.

    Attributes:
        name: The subcommand name. Derived *from* this registry entry.
        help_text: One line, shown by ``--help``.
        columns: Column order for the table form.
        rows: Produces the rows. Receives an open **read-only** store and the
            parsed arguments.
        requires_project: Whether ``--project`` is required.
        flags: Extra boolean flags, as ``(flag, help)`` pairs.
    """

    name: str
    help_text: str
    columns: tuple[str, ...]
    rows: Callable[[Store, argparse.Namespace], list[Row]]
    requires_project: bool = True
    flags: tuple[tuple[str, str], ...] = field(default_factory=tuple)


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


#: The listing registry — the single structural definition of what ``inspect``
#: can show. Adding a listing is appending here; nothing else changes.
#:
#: ``projects`` is handled separately in :func:`run_listing` because it reads
#: the supervisor directory rather than one store, so it has no ``--project``
#: and opens nothing.
LISTINGS: tuple[Listing, ...] = (
    Listing(
        name="projects",
        help_text="Project ids that have a store in the supervisor directory.",
        columns=("project_id", "store"),
        rows=lambda store, args: [],
        requires_project=False,
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
)

#: By name, so dispatch is a lookup rather than a chain of comparisons.
LISTINGS_BY_NAME: dict[str, Listing] = {listing.name: listing for listing in LISTINGS}

#: The listing that reads the supervisor directory rather than a single store.
PROJECTS_LISTING = "projects"


def _project_rows() -> list[Row]:
    """Project ids with a store in the supervisor directory.

    An empty supervisor directory yields an empty list rather than failing: a
    supervisor that has never run is a valid state.
    """
    store_dir = paths.store_dir()
    return [
        {
            "project_id": project_id,
            "store": str(store_path_for(store_dir, project_id)),
        }
        for project_id in discover_project_ids(store_dir)
    ]


def run_listing(name: str, args: argparse.Namespace, *, use_json: bool) -> ExitCode:
    """Run one listing and print it.

    Raises:
        StoreError: If the project's store cannot be opened read-only — which
            includes a store needing migration, since inspection never
            migrates. Mapped to an exit code by the boundary handler.
    """
    from amoeba.cli.main import ExitCode

    listing = LISTINGS_BY_NAME[name]

    if name == PROJECTS_LISTING:
        rows = _project_rows()
    else:
        store_path = store_path_for(paths.store_dir(), args.project)
        with Store.open_read_only(store_path) as store:
            rows = listing.rows(store, args)

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
