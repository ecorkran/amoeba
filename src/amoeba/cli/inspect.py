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
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from amoeba.cli import (
    inspect_cf,
    inspect_checks,
    inspect_evidence,
    inspect_feed,
    inspect_inbox,
)
from amoeba.inspection.listing import (
    NODE_OPTION,
    FlagOption,
    Listing,
    ListingRequest,
    ListingScope,
    OptionValue,
    Row,
)
from amoeba.process.supervisor import store_path_for
from amoeba.store import Store, paths
from amoeba.store.discovery import discover_project_ids

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode

UNRESOLVED_OPTION = FlagOption(
    name="unresolved", help_text="Only entries still in flight."
)


def _node_rows(store: Store, request: ListingRequest) -> list[Row]:
    """Every node in a project."""
    return [
        {
            "id": node.id,
            "kind": node.kind.value,
            "status": node.status.value,
            "title": node.title,
            "parent_id": node.parent_id or "",
        }
        for node in store.nodes_for_project(request.require_project_id())
    ]


def _blocked_rows(store: Store, request: ListingRequest) -> list[Row]:
    """Every blocked node, with what it is blocked on."""
    return [
        {
            "node_id": blocked.node.id,
            "title": blocked.node.title,
            "blocked_on": blocked.blocked_state.kind.value,
            "context": blocked.blocked_state.context,
        }
        for blocked in store.blocked(request.require_project_id())
    ]


def _journal_rows(store: Store, request: ListingRequest) -> list[Row]:
    """Journal entries for a project, optionally only the unresolved ones."""
    entries = store.journal_entries(
        request.require_project_id(),
        include_resolved=not request.option(UNRESOLVED_OPTION),
    )
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
        flags=(UNRESOLVED_OPTION,),
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
        choice_options=(inspect_inbox.CHANNEL_OPTION,),
    ),
    Listing(
        name="verdicts",
        help_text="Recorded review verdicts for a project, in arrival order.",
        columns=inspect_evidence.VERDICT_COLUMNS,
        rows=inspect_evidence.verdict_rows,
        value_options=(NODE_OPTION, inspect_evidence.JUDGE_INVOCATION_OPTION),
    ),
    Listing(
        name="findings",
        help_text="Findings by content key, with how often each was seen.",
        columns=inspect_evidence.FINDING_COLUMNS,
        rows=inspect_evidence.finding_rows,
        value_options=(NODE_OPTION,),
    ),
    Listing(
        name="changes",
        help_text="One review's findings as new, recurring, or gone.",
        columns=inspect_evidence.CHANGE_COLUMNS,
        rows=inspect_evidence.change_rows,
        value_options=(inspect_evidence.VERDICT_OPTION,),
    ),
    Listing(
        name="checks",
        help_text="Recorded check results, with the standing each one earns.",
        columns=inspect_checks.CHECK_COLUMNS,
        rows=inspect_checks.check_rows,
        value_options=(NODE_OPTION,),
    ),
    Listing(
        name="calibration",
        help_text="Descriptive judge-sample counts by review type and model.",
        columns=inspect_checks.CALIBRATION_LISTING_COLUMNS,
        rows=inspect_checks.calibration_rows,
    ),
    Listing(
        name="watches",
        help_text="Registered review directories and their detection state.",
        columns=inspect_feed.WATCH_COLUMNS,
        rows=inspect_feed.watch_rows,
    ),
    Listing(
        name="detections",
        help_text="Review files detection examined, in detection order.",
        columns=inspect_feed.DETECTION_COLUMNS,
        rows=inspect_feed.detection_rows,
        choice_options=(inspect_feed.OUTCOME_OPTION,),
    ),
    Listing(
        name="cf-links",
        help_text="Context Forge projects this project watches.",
        columns=inspect_cf.LINK_COLUMNS,
        rows=inspect_cf.link_rows,
    ),
    Listing(
        name="cf-snapshots",
        help_text="What the Context Forge watch recorded, with the fields that moved.",
        columns=inspect_cf.SNAPSHOT_COLUMNS,
        rows=inspect_cf.snapshot_rows,
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

    request = listing_request(listing, args)

    if listing.supervisor_rows is not None:
        rows = listing.supervisor_rows(supervisor_dir)
    elif listing.rows is not None:
        project_store_file = store_path_for(
            supervisor_dir, request.require_project_id()
        )
        with Store.open_read_only(project_store_file) as store:
            rows = listing.rows(store, request)
    else:
        raise ValueError(f"listing {name!r} declares no rows")

    if use_json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        _print_table(listing.columns, rows)

    return ExitCode.OK


def listing_request(listing: Listing, args: argparse.Namespace) -> ListingRequest:
    """The request one listing's parsed arguments describe.

    Each option's value is read by its ``name``, which is the ``dest`` the
    parser stores it under. ``compact`` is the table form.
    """
    options: dict[str, OptionValue] = {
        option.name: getattr(args, option.name)
        for option in (*listing.flags, *listing.choice_options, *listing.value_options)
    }
    project_id = args.project if listing.scope is ListingScope.PROJECT else None
    return ListingRequest(project_id=project_id, options=options, compact=not args.json)


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
