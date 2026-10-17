"""Rows for the ``cf-links`` and ``cf-snapshots`` listings.

A sibling of ``inspect_checks.py``: this module holds the columns and the row
functions, and ``inspect.py`` registers them in its one ``LISTINGS`` registry.
Both receive a **read-only** store, so they work whether or not the resident
process is running.

A snapshot's ``changed`` is a list of objects. The table shows the names of the
fields that moved in ``changed_fields``; ``--json`` carries the full list as
``changed`` beside it, since the table prints only the declared columns.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from amoeba.store import Store

if TYPE_CHECKING:  # pragma: no cover - typing only; inspect.py imports this
    from amoeba.cli.inspect import Row

LINK_COLUMNS: Final = ("cf_project_id", "linked_at")

SNAPSHOT_COLUMNS: Final = (
    "id",
    "observed_at",
    "cf_project_id",
    "outcome",
    "changed_fields",
    "detail",
    "cf_updated_at",
)

_FIELD_KEY: Final = "field"


def link_rows(store: Store, args: argparse.Namespace) -> list[Row]:
    """A project's Context Forge links, in the order they were linked."""
    return [
        {
            "cf_project_id": link.cf_project_id,
            "linked_at": link.linked_at.isoformat(),
        }
        for link in store.cf_links(args.project)
    ]


def _field_names(changed: Sequence[Mapping[str, object]] | None) -> str:
    """The distinct names of the fields that moved, in order; empty if none."""
    names: list[str] = []
    for change in changed or ():
        name = change.get(_FIELD_KEY)
        if isinstance(name, str) and name not in names:
            names.append(name)
    return ", ".join(names)


def snapshot_rows(store: Store, args: argparse.Namespace) -> list[Row]:
    """A project's snapshots in id order."""
    return [
        {
            "id": snapshot.id,
            "observed_at": snapshot.observed_at.isoformat(),
            "cf_project_id": snapshot.cf_project_id,
            "outcome": snapshot.outcome.value,
            "changed_fields": _field_names(snapshot.changed),
            "detail": snapshot.detail or "",
            "cf_updated_at": snapshot.cf_updated_at or "",
            "changed": None if snapshot.changed is None else list(snapshot.changed),
            "state": None if snapshot.state is None else dict(snapshot.state),
            "cf_version_label": snapshot.cf_version_label,
        }
        for snapshot in store.cf_snapshots(args.project)
    ]
