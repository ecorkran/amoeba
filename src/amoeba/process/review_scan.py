"""The per-file detection path: digest, ledger check, parse, attribute, record.

Called by ``ReviewDetectionTenant`` for each settled file. Nothing here is
guessed: a file that does not parse is ``unparseable``, a review with no single
slice node is ``unattributed``, and only an attributed review becomes a verdict
(LLD "Detecting a review"). Both refusals are terminal for that digest; changed
bytes make a new digest.

This module and the tenant are the only ones that know both 105's parser and
the store's write path.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable

from amoeba.process.review_sources import DetectedFile
from amoeba.store import (
    DetectionInput,
    DetectionOutcome,
    Store,
    attribute_review,
)
from amoeba.upstream.squadron import (
    ParsedReview,
    SquadronReviewError,
    parse_review_artifact,
    review_record_id,
    to_verdict_input,
)

logger = logging.getLogger(__name__)


def content_digest(content: bytes) -> str:
    """The ledger's digest: sha256 of the bytes examined."""
    return hashlib.sha256(content).hexdigest()


def recording[ResultT](
    project_id: str, path: str, write: Callable[[], ResultT]
) -> ResultT:
    """Run one store write; on failure log at ERROR naming it, and re-raise.

    A store that cannot record a row is sick. Continuing past it would hide
    that, so the exception stops the process (LLD Errors).
    """
    try:
        return write()
    except Exception:
        logger.exception(
            "cannot record review detection for %s in project %s", path, project_id
        )
        raise


def examine(
    store: Store, project_id: str, detected: DetectedFile, version_label: str
) -> bool:
    """Examine one settled file. Returns whether a ledger row was written."""
    path = str(detected.path)
    digest = content_digest(detected.content)
    if store.detection(project_id, path, digest) is not None:
        return False

    def record(outcome: DetectionOutcome, **fields: str | None) -> None:
        detection = DetectionInput(project_id, path, digest, outcome, **fields)
        recording(project_id, path, lambda: store.record_detection(detection))

    try:
        parsed = parse_review_artifact(detected.content.decode("utf-8"))
    except (SquadronReviewError, UnicodeDecodeError) as error:
        # Specific: not a review this parser can read. An outcome, not an
        # exception; retried only if the bytes change.
        logger.info("review file %s is unparseable: %s", path, error)
        record(DetectionOutcome.UNPARSEABLE, detail=str(error))
        return True

    record_id = review_record_id(parsed)
    attribution = (
        attribute_review(store.nodes_for_project(project_id), parsed.slice)
        if parsed.slice is not None
        else None
    )
    if attribution is None or attribution.node_id is None:
        candidates = () if attribution is None else attribution.candidates
        logger.info("review file %s is unattributed: %s", path, list(candidates))
        record(
            DetectionOutcome.UNATTRIBUTED,
            record_id=record_id,
            detail=_candidates_detail(parsed, candidates),
        )
        return True

    node_id = attribution.node_id
    try:
        verdict = to_verdict_input(
            parsed,
            node_id=node_id,
            record_id=record_id,
            # The file's own stamp wins; the start-up label is only the
            # fallback, and 105 refuses a label that disagrees with a stamp.
            upstream_version=(
                version_label if parsed.upstream_version is None else None
            ),
            source_path=path,
        )
    except SquadronReviewError as error:
        # Specific: parsed, but its stamp is unusable (an empty label). Not a
        # review this slice can record, so the same outcome as a parse error.
        logger.info("review file %s cannot be recorded: %s", path, error)
        record(DetectionOutcome.UNPARSEABLE, record_id=record_id, detail=str(error))
        return True
    detection = DetectionInput(
        project_id, path, digest, DetectionOutcome.INGESTED, record_id=record_id
    )
    recording(
        project_id, path, lambda: store.record_detected_verdict(verdict, detection)
    )
    logger.info("ingested review %s as verdict %s on %s", path, record_id, node_id)
    return True


def _candidates_detail(parsed: ParsedReview, candidates: tuple[str, ...]) -> str:
    if parsed.slice is None:
        return "review carries no slice; candidates: []"
    return f"slice {parsed.slice!r}; candidates: {list(candidates)}"
