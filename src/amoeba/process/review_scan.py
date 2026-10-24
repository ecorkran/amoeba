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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from amoeba.store import (
    DetectionInput,
    DetectionOutcome,
    ReviewWatch,
    Store,
    attribute_review,
)
from amoeba.store.review_sources import DetectedFile
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


def ledger_key(path: Path, content: bytes) -> tuple[str, str]:
    """The ledger's ``(path, digest)`` key for a file's path and the bytes read.

    The one place the pair is formed: baselining, examining and
    :func:`detection_key` all call it, so the three cannot drift apart.
    """
    return str(path), content_digest(content)


def detection_key(
    watches: Sequence[ReviewWatch], file: Path, content: bytes
) -> tuple[str, str] | None:
    """The key detection would give ``file``, whose bytes are ``content``.

    The Runner calls this on a review file it read (slice 125, D7) so that its
    record and detection's ledger row collide on one key. The file's directory
    must be a watch's ``reviews_dir``: the path is that directory joined with
    the file name, as the directory source builds it, so a watch given with a
    trailing separator matches too. ``None`` means no watch covers the file;
    detection never sees such a file, and the caller keys it by its own path.

    ``content`` is passed in, rather than read here, so the file is read once.
    """
    for watch in watches:
        directory = Path(watch.reviews_dir)
        if directory == file.parent:
            return ledger_key(directory / file.name, content)
    return None


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


@dataclass(frozen=True)
class _Examined:
    """One file under examination: the ledger key, and where to record it."""

    store: Store
    project_id: str
    path: str
    digest: str

    def refuse(
        self, outcome: DetectionOutcome, *, detail: str, record_id: str | None = None
    ) -> None:
        """Record a terminal refusal for this ``(path, digest)``."""
        logger.info("review file %s is %s: %s", self.path, outcome.value, detail)
        detection = DetectionInput(
            self.project_id,
            self.path,
            self.digest,
            outcome,
            record_id=record_id,
            detail=detail,
        )
        recording(
            self.project_id, self.path, lambda: self.store.record_detection(detection)
        )


def examine(
    store: Store, project_id: str, detected: DetectedFile, version_label: str
) -> bool:
    """Examine one settled file. Returns whether a ledger row was written."""
    path, digest = ledger_key(detected.path, detected.content)
    if store.detection(project_id, path, digest) is not None:
        return False
    examined = _Examined(store, project_id, path, digest)

    try:
        parsed = parse_review_artifact(detected.content.decode("utf-8"))
    except (SquadronReviewError, UnicodeDecodeError) as error:
        # Specific: not a review this parser can read. An outcome, not an
        # exception; retried only if the bytes change.
        examined.refuse(DetectionOutcome.UNPARSEABLE, detail=str(error))
        return True

    record_id = review_record_id(parsed)
    node_id = _attributed_node(examined, parsed, record_id)
    if node_id is not None:
        _ingest(examined, parsed, record_id, node_id, version_label)
    return True


def _attributed_node(
    examined: _Examined, parsed: ParsedReview, record_id: str
) -> str | None:
    """The review's slice node; ``None`` after recording ``unattributed``."""
    if parsed.slice is None:
        candidates: tuple[str, ...] = ()
        detail = "review carries no slice; candidates: []"
    else:
        nodes = examined.store.nodes_for_project(examined.project_id)
        attribution = attribute_review(nodes, parsed.slice)
        if attribution.node_id is not None:
            return attribution.node_id
        candidates = attribution.candidates
        detail = f"slice {parsed.slice!r}; candidates: {list(candidates)}"
    examined.refuse(DetectionOutcome.UNATTRIBUTED, detail=detail, record_id=record_id)
    return None


def _ingest(
    examined: _Examined,
    parsed: ParsedReview,
    record_id: str,
    node_id: str,
    version_label: str,
) -> None:
    """Record the verdict and its ``ingested`` row in one transaction."""
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
            source_path=examined.path,
        )
    except SquadronReviewError as error:
        # Specific: parsed, but its stamp is unusable (an empty label). Not a
        # review this slice can record, so the same outcome as a parse error.
        examined.refuse(
            DetectionOutcome.UNPARSEABLE, detail=str(error), record_id=record_id
        )
        return
    detection = DetectionInput(
        examined.project_id,
        examined.path,
        examined.digest,
        DetectionOutcome.INGESTED,
        record_id=record_id,
    )
    recording(
        examined.project_id,
        examined.path,
        lambda: examined.store.record_detected_verdict(verdict, detection),
    )
    logger.info(
        "ingested review %s as verdict %s on %s", examined.path, record_id, node_id
    )
