"""A run's last review: select, read, parse and attribute it (D7).

The run's outcome document lists the review files it wrote. The last entry is the
run's review: its ``paths`` (the parts of a split review) in order if it has them,
otherwise its ``path``. Each file is read once and whole, parsed with 105's parser
exactly as detection parses it, and attributed to a slice node. The ledger key it
is recorded under comes from ``detection_key``, so detection never takes the file
as new.

Anything that makes the review unreadable, unparseable or misattributed makes the
whole run's review :class:`ReviewUnknown`, and nothing is recorded. That is an
answer, not an exception; the caller decides what a human sees.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from amoeba.process import RunOutcomeDocument, RunReview, detection_key, ledger_key
from amoeba.store import (
    DetectionInput,
    DetectionOutcome,
    Node,
    ReviewWatch,
    RunnerReview,
    attribute_review,
)
from amoeba.upstream.squadron import (
    ParsedReview,
    SquadronReviewError,
    parse_review_artifact,
    review_record_id,
    to_verdict_input,
)


@dataclass(frozen=True)
class ReviewFiles:
    """The reviews to record, in part order. Empty when the run wrote none."""

    reviews: tuple[RunnerReview, ...]


@dataclass(frozen=True)
class ReviewUnknown:
    """The run's review cannot be recorded. ``path`` is the file at fault, if any."""

    path: str | None
    reason: str


@dataclass(frozen=True)
class ReviewScope:
    """What the Runner knows about the run that attribution and recording need."""

    project_id: str
    run_id: str
    checkout: Path
    #: The slice node that is the run's step's parent: the only valid attribution.
    slice_node_id: str
    slice_nodes: Sequence[Node]
    watches: Sequence[ReviewWatch]
    #: The ``sq --version`` label, captured once; a file's own stamp wins over it.
    version_label: str


def select_review_files(
    document: RunOutcomeDocument, scope: ReviewScope
) -> ReviewFiles | ReviewUnknown:
    """Read, parse and attribute the run's last review, or say why not."""
    if not document.reviews:
        return ReviewFiles(())
    paths = _selected_paths(document.reviews[-1])
    if isinstance(paths, ReviewUnknown):
        return paths
    reviews: list[RunnerReview] = []
    for relative in paths:
        review = _load(scope.checkout / relative, scope)
        if isinstance(review, ReviewUnknown):
            return review
        reviews.append(review)
    return ReviewFiles(tuple(reviews))


def _selected_paths(entry: RunReview) -> list[str] | ReviewUnknown:
    """The files of the last entry: its parts if split, else its one path."""
    if entry.paths is not None:
        return entry.paths
    if entry.path is not None:
        return [entry.path]
    return ReviewUnknown(None, "the run's last review lists neither path nor paths")


def _load(file: Path, scope: ReviewScope) -> RunnerReview | ReviewUnknown:
    shown = str(file)
    try:
        content = file.read_bytes()
    except FileNotFoundError:
        # Specific: the run listed a file it did not leave. An answer.
        return ReviewUnknown(shown, "the review file is missing")
    except OSError as error:
        # Specific: unreadable (permissions, a directory). An answer.
        return ReviewUnknown(shown, f"the review file is unreadable: {error}")
    try:
        parsed = parse_review_artifact(content.decode("utf-8"))
    except (SquadronReviewError, UnicodeDecodeError) as error:
        # Specific: not a review this parser can read.
        return ReviewUnknown(shown, f"the review file does not parse: {error}")
    unattributed = _attribution_fault(parsed, scope)
    if unattributed is not None:
        return ReviewUnknown(shown, unattributed)
    return _recorded(file, content, parsed, scope)


def _attribution_fault(parsed: ParsedReview, scope: ReviewScope) -> str | None:
    """Why the review is not the step's slice's, or ``None`` if it is."""
    if parsed.slice is None:
        return "the review carries no slice"
    attribution = attribute_review(scope.slice_nodes, parsed.slice)
    if attribution.node_id is None:
        return (
            f"slice {parsed.slice!r} matches no single node; "
            f"candidates: {list(attribution.candidates)}"
        )
    if attribution.node_id != scope.slice_node_id:
        return (
            f"slice {parsed.slice!r} is node {attribution.node_id}, "
            f"not the step's slice node {scope.slice_node_id}"
        )
    return None


def _recorded(
    file: Path, content: bytes, parsed: ParsedReview, scope: ReviewScope
) -> RunnerReview | ReviewUnknown:
    key = detection_key(scope.watches, file, content)
    path, digest = key if key is not None else ledger_key(file.resolve(), content)
    record_id = review_record_id(parsed)
    try:
        verdict = to_verdict_input(
            parsed,
            node_id=scope.slice_node_id,
            record_id=record_id,
            # The file's own stamp wins; the start-up label is only the fallback.
            upstream_version=(
                scope.version_label if parsed.upstream_version is None else None
            ),
            source_path=path,
        )
    except SquadronReviewError as error:
        # Specific: parsed, but its version stamp or the label is unusable.
        return ReviewUnknown(str(file), f"the review's version is unusable: {error}")
    detection = DetectionInput(
        scope.project_id,
        path,
        digest,
        DetectionOutcome.RUNNER_ISSUED,
        record_id=record_id,
    )
    return RunnerReview(dataclasses.replace(verdict, sq_run_id=scope.run_id), detection)
