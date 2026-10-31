"""Rows for the core listings: ``projects``, ``nodes``, ``blocked``, and ``journal``.

The one ``LISTINGS`` registry registers these. ``projects`` reads the supervisor
directory and opens no store; the rest receive a **read-only** store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from amoeba.inspection.listing import FlagOption, ListingRequest, Row
from amoeba.store import Channel, Store, paths
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
    """Every blocked node in one project, with what it is blocked on."""
    return _blocked_rows(store, request.require_project_id())


#: The ``reason`` of a block whose escalation recorded none (a judge or
#: checkpoint block, or a human block without a payload reason).
NO_REASON_RECORDED: Final = "(no reason recorded)"


def all_blocked_rows(store_dir: Path) -> list[Row]:
    """Every blocked node in every project, each store opened read-only."""
    rows: list[Row] = []
    for project_id in discover_project_ids(store_dir):
        with Store.open_read_only(
            paths.project_store_path(store_dir, project_id)
        ) as store:
            with store.read_transaction():
                rows.extend(_blocked_rows(store, project_id))
    return rows


def _blocked_rows(store: Store, project_id: str) -> list[Row]:
    """The blocked rows of one project; ``payload`` is the escalation's, in full."""
    payloads = {
        message.blocked_state_id: dict(message.payload or {})
        for message in store.messages(project_id, channel=Channel.ESCALATION)
        if message.blocked_state_id is not None
    }
    rows: list[Row] = []
    for blocked in store.blocked(project_id):
        payload = payloads.get(blocked.blocked_state.id, {})
        rows.append(
            {
                "project_id": project_id,
                "node_id": blocked.node.id,
                "title": blocked.node.title,
                "blocked_on": blocked.blocked_state.kind.value,
                "reason": payload.get("reason")
                or payload.get("fault_kind")
                or NO_REASON_RECORDED,
                "context": blocked.blocked_state.context,
                # The id a resolution names (slice 127).
                "blocked_state_id": blocked.blocked_state.id,
                "payload": payload,
            }
        )
    return rows


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
