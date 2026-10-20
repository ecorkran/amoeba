"""``amoeba inspect``: argparse helpers and printing over ``amoeba.inspection``.

The listing registry and every row function live in ``amoeba.inspection``; this
module turns parsed arguments into a :class:`ListingRequest`, calls
:func:`read_listing`, and prints the rows as a table or as JSON.

``tests/test_writer_guard.py`` enforces mechanically that this module never
reaches for the read-write open.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from amoeba.inspection import (
    LISTINGS_BY_NAME,
    Listing,
    ListingRequest,
    ListingScope,
    OptionValue,
    Row,
    read_listing,
)
from amoeba.store import paths

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode


def run_listing(name: str, args: argparse.Namespace, *, use_json: bool) -> ExitCode:
    """Run one listing and print it.

    Raises:
        StoreError: If the project's store cannot be opened read-only — which
            includes a store needing migration, since inspection never
            migrates. Mapped to an exit code by the boundary handler.
    """
    from amoeba.cli.main import ExitCode

    listing = LISTINGS_BY_NAME[name]
    request = listing_request(listing, args, compact=not use_json)
    result = read_listing(name, request, paths.store_dir())

    if use_json:
        print(json.dumps(result.rows, indent=2, default=str))
    else:
        _print_table(listing.columns, result.rows)

    return ExitCode.OK


def listing_request(
    listing: Listing, args: argparse.Namespace, *, compact: bool
) -> ListingRequest:
    """The request one listing's parsed arguments describe.

    Each option's value is read by its ``name``, which is the ``dest`` the
    parser stores it under. ``compact`` is the table form.
    """
    options: dict[str, OptionValue] = {
        option.name: getattr(args, option.name) for option in listing.options
    }
    project_id = args.project if listing.scope is ListingScope.PROJECT else None
    return ListingRequest(project_id=project_id, options=options, compact=compact)


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
