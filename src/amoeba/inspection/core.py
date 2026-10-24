"""Rows for the core listings: ``projects``, ``nodes``, ``blocked``, and ``journal``.

The one ``LISTINGS`` registry registers these. ``projects`` reads the supervisor
directory and opens no store; the rest receive a **read-only** store.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.inspection.listing import FlagOption, ListingRequest, Row
from amoeba.store import Store, paths
from amoeba.store.discovery import discover_project_ids

UNRESOLVED_OPTION = FlagOption(
    name="unresolved", help_text="Only entries still in flight."
)


def node_rows(store: Store, request: ListingRequest) -> list[Row]:
    """Every node in a project."""
    return [
        {
            "id": node.id,
            "kind": node.kind.value,
            "status": node.status.value,
            "title": node.title,
            "parent_id": node.parent_id,
            "cf_index": node.cf.index,
        }
        for node in store.nodes_for_project(request.require_project_id())
    ]


def blocked_rows(store: Store, request: ListingRequest) -> list[Row]:
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


def journal_rows(store: Store, request: ListingRequest) -> list[Row]:
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
            "awaits_routing": entry.awaits_routing,
            "issued_at": entry.issued_at.isoformat() if entry.issued_at else "",
            "parameters": entry.parameters,
            "result": entry.result if entry.result is not None else {},
        }
        for entry in entries
    ]


def project_rows(supervisor_dir: Path) -> list[Row]:
    """Project ids with a store in the supervisor directory.

    An empty supervisor directory yields an empty list rather than failing: a
    supervisor that has never run is a valid state.
    """
    return [
        {
            "project_id": project_id,
            "store": str(paths.project_store_path(supervisor_dir, project_id)),
        }
        for project_id in discover_project_ids(supervisor_dir)
    ]
