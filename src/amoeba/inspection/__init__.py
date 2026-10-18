"""Read-only listings over store contents, shared by ``amoeba inspect`` and the server.

Every listing is declared in **one registry**, :data:`LISTINGS`. The registry is
the structural definition: CLI subcommand names and URL listing names derive
from it, never the reverse — a user-visible label is not logical structure.
Adding a listing is appending a :class:`Listing` here.

:func:`read_listing` is the one read path: it opens a project store with
:meth:`Store.open_read_only`, which never migrates, never creates, and refuses
writes, and reads the rows and the feed head in one snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amoeba.inspection import cf, checks, core, evidence, feed, inbox
from amoeba.inspection.listing import (
    NODE_OPTION,
    ChoiceOption,
    FlagOption,
    Listing,
    ListingOption,
    ListingRequest,
    ListingScope,
    OptionValue,
    Row,
    ValueOption,
)
from amoeba.store import Store, paths

__all__ = [
    "LISTINGS",
    "LISTINGS_BY_NAME",
    "NODE_OPTION",
    "PROJECTS_LISTING",
    "ChoiceOption",
    "FlagOption",
    "Listing",
    "ListingOption",
    "ListingRequest",
    "ListingResult",
    "ListingScope",
    "OptionValue",
    "Row",
    "ValueOption",
    "read_listing",
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
        supervisor_rows=core.project_rows,
    ),
    Listing(
        name="inbox",
        help_text="Inbox files that are pending, quarantined, or failed.",
        columns=("state", "file", "attempts", "reason", "problem"),
        supervisor_rows=inbox.inbox_rows,
    ),
    Listing(
        name="nodes",
        help_text="Lifecycle nodes for a project.",
        columns=("id", "kind", "status", "title", "parent_id"),
        rows=core.node_rows,
    ),
    Listing(
        name="blocked",
        help_text="Blocked nodes for a project, and what each is blocked on.",
        columns=("node_id", "title", "blocked_on", "context"),
        rows=core.blocked_rows,
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
        rows=core.journal_rows,
        flags=(core.UNRESOLVED_OPTION,),
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
        rows=inbox.submission_rows,
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
        rows=inbox.message_rows,
        choice_options=(inbox.CHANNEL_OPTION,),
    ),
    Listing(
        name="verdicts",
        help_text="Recorded review verdicts for a project, in arrival order.",
        columns=evidence.VERDICT_COLUMNS,
        rows=evidence.verdict_rows,
        value_options=(NODE_OPTION, evidence.JUDGE_INVOCATION_OPTION),
    ),
    Listing(
        name="findings",
        help_text="Findings by content key, with how often each was seen.",
        columns=evidence.FINDING_COLUMNS,
        rows=evidence.finding_rows,
        value_options=(NODE_OPTION,),
    ),
    Listing(
        name="changes",
        help_text="One review's findings as new, recurring, or gone.",
        columns=evidence.CHANGE_COLUMNS,
        rows=evidence.change_rows,
        value_options=(evidence.VERDICT_OPTION,),
    ),
    Listing(
        name="checks",
        help_text="Recorded check results, with the standing each one earns.",
        columns=checks.CHECK_COLUMNS,
        rows=checks.check_rows,
        value_options=(NODE_OPTION,),
    ),
    Listing(
        name="calibration",
        help_text="Descriptive judge-sample counts by review type and model.",
        columns=checks.CALIBRATION_LISTING_COLUMNS,
        rows=checks.calibration_rows,
    ),
    Listing(
        name="watches",
        help_text="Registered review directories and their detection state.",
        columns=feed.WATCH_COLUMNS,
        rows=feed.watch_rows,
    ),
    Listing(
        name="detections",
        help_text="Review files detection examined, in detection order.",
        columns=feed.DETECTION_COLUMNS,
        rows=feed.detection_rows,
        choice_options=(feed.OUTCOME_OPTION,),
    ),
    Listing(
        name="cf-links",
        help_text="Context Forge projects this project watches.",
        columns=cf.LINK_COLUMNS,
        rows=cf.link_rows,
    ),
    Listing(
        name="cf-snapshots",
        help_text="What the Context Forge watch recorded, with the fields that moved.",
        columns=cf.SNAPSHOT_COLUMNS,
        rows=cf.snapshot_rows,
    ),
)

#: By name, so dispatch is a lookup rather than a chain of comparisons.
LISTINGS_BY_NAME: dict[str, Listing] = {listing.name: listing for listing in LISTINGS}


@dataclass(frozen=True)
class ListingResult:
    """One listing's rows, and the feed ``seq`` they are current as of.

    ``as_of_seq`` is ``None`` for a supervisor-level listing, which reads no
    project's feed.
    """

    rows: list[Row]
    as_of_seq: int | None


def read_listing(name: str, request: ListingRequest, store_dir: Path) -> ListingResult:
    """Run one listing against the supervisor directory ``store_dir``.

    Raises:
        KeyError: For a name that is not in the registry.
        ValueError: For a project-scoped listing asked without a project.
        StoreError: If the project's store cannot be opened read-only — which
            includes a store needing migration, since inspection never migrates.
    """
    listing = LISTINGS_BY_NAME[name]
    if listing.supervisor_rows is not None:
        return ListingResult(rows=listing.supervisor_rows(store_dir), as_of_seq=None)
    if listing.rows is None:
        raise ValueError(f"listing {name!r} declares no rows")
    project_id = request.require_project_id()
    with Store.open_read_only(paths.project_store_path(store_dir, project_id)) as store:
        return ListingResult(rows=listing.rows(store, request), as_of_seq=None)
