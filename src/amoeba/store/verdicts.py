"""Recording review verdicts, and reading them back.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

``record_verdict`` is one transaction: the retry check, the checks, the verdict
row, and one observation row per finding commit together or not at all. The
caller supplies the id, so recording again after a crash is harmless: the first
record wins, and a WARNING says so if the content differs.
"""

from __future__ import annotations

import dataclasses
import logging

from amoeba.store import sql_inbox
from amoeba.store._base import isoformat, now
from amoeba.store._verdict_writer import VerdictWriter
from amoeba.store.evidence_models import VerdictInput, VerdictRecord
from amoeba.store.models import NodeNotFoundError, StoreIntegrityError

logger = logging.getLogger(__name__)

_INPUT_FIELDS = tuple(field.name for field in dataclasses.fields(VerdictInput))


def _as_input(record: VerdictRecord) -> VerdictInput:
    return VerdictInput(**{name: getattr(record, name) for name in _INPUT_FIELDS})


class VerdictOperations(VerdictWriter):
    """Record a review's verdict and findings; read verdicts and findings back."""

    def record_verdict(
        self, verdict: VerdictInput, *, project_id: str
    ) -> VerdictRecord:
        """Record one review result and its findings in one transaction.

        Args:
            verdict: The already-parsed review result. Its ``id`` is the retry
                key.
            project_id: The project the review belongs to; the node must be in
                it.

        Returns:
            The new record or, when the id is already recorded, the existing one.

        Raises:
            NodeNotFoundError: If the node does not exist in ``project_id``.
            ValueError: If any other check fails: a journal entry on another
                node, a provider failure with findings or a verdict other than
                ``UNKNOWN``, or an empty ``upstream_version``. Nothing is written.
        """
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            existing = self._load_verdict(verdict.id)
            if existing is not None:
                if existing.project_id != project_id or _as_input(existing) != verdict:
                    logger.warning(
                        "verdict %r is already recorded with different content; "
                        "keeping the first",
                        verdict.id,
                    )
                return existing

            rejection = self._verdict_rejection(project_id, verdict)
            if rejection is not None:
                if rejection.node_missing:
                    raise NodeNotFoundError(rejection.reason)
                raise ValueError(rejection.reason)

            self._insert_verdict(project_id, verdict, isoformat(now()))
            recorded = self._load_verdict(verdict.id)

        if recorded is None:
            raise StoreIntegrityError(f"verdict {verdict.id!r} vanished after insert")
        return recorded
