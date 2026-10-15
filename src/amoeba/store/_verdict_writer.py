"""The store's one internal verdict writer.

Every verdict is checked and written here — by ``record_verdict`` and by the
inbox's ``verdict`` effect alike — so both paths run the same checks. The check
returns a reason rather than raising: a direct call raises on it, and the inbox
records it as a rejection, tested as a plain branch. The insert never commits;
it runs inside the caller's transaction.

A base class rather than a method on ``VerdictOperations``, so the inbox does
not import a sibling operation class (the pattern ``BlockWriter`` set).
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from amoeba.store import sql_evidence, sql_journal
from amoeba.store._base import StoreBase, isoformat, now
from amoeba.store.evidence_models import (
    FindingObservation,
    VerdictInput,
    VerdictRecord,
    provider_failure_problem,
)
from amoeba.store.mapping_evidence import (
    map_observation,
    map_verdict,
    observation_as_finding,
    observation_parameters,
    verdict_parameters,
)
from amoeba.store.mapping_journal import map_journal_entry
from amoeba.store.models import NodeNotFoundError, StoreIntegrityError
from amoeba.store.verdict_payload import verdict_from_payload

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerdictRejection:
    """Why a verdict cannot be recorded. ``node_missing`` selects the error type."""

    reason: str
    node_missing: bool = False


_INPUT_FIELDS = tuple(field.name for field in dataclasses.fields(VerdictInput))


def _as_input(record: VerdictRecord) -> VerdictInput:
    return VerdictInput(**{name: getattr(record, name) for name in _INPUT_FIELDS})


class VerdictWriter(StoreBase):
    """Checks and writes one verdict and its findings. Never commits."""

    def _verdict_rejection(
        self, project_id: str, verdict: VerdictInput
    ) -> VerdictRejection | None:
        """Every check after the retry rule, in the LLD's order; ``None`` passes."""
        node = self.get_node(verdict.node_id)
        if node is None or node.project_id != project_id:
            return VerdictRejection(
                f"no node {verdict.node_id!r} in project {project_id!r}",
                node_missing=True,
            )
        if verdict.journal_entry_id is not None:
            row = self._execute(
                sql_journal.SELECT_JOURNAL_ENTRY_BY_ID, (verdict.journal_entry_id,)
            ).fetchone()
            if row is None or map_journal_entry(row).node_id != verdict.node_id:
                return VerdictRejection(
                    f"journal entry {verdict.journal_entry_id!r} is not on node "
                    f"{verdict.node_id!r}"
                )
        failure_problem = provider_failure_problem(
            provider_failure=verdict.provider_failure,
            verdict=verdict.verdict,
            findings=verdict.findings,
        )
        if failure_problem is not None:
            return VerdictRejection(failure_problem)
        if not verdict.provenance.upstream_version.strip():
            return VerdictRejection("upstream_version must not be empty")
        return None

    def _insert_verdict(
        self, project_id: str, verdict: VerdictInput, recorded_at: str
    ) -> None:
        """Write the verdict row, then one observation row per finding, in order."""
        self._execute(
            sql_evidence.INSERT_VERDICT,
            verdict_parameters(verdict, project_id, recorded_at),
        )
        for ordinal, finding in enumerate(verdict.findings):
            self._execute(
                sql_evidence.INSERT_OBSERVATION,
                observation_parameters(verdict.id, ordinal, finding),
            )

    def _record_verdict_within(
        self, verdict: VerdictInput, project_id: str
    ) -> VerdictRecord:
        """``record_verdict``'s body, inside a transaction the caller opened.

        The retry rule, then the checks, then the insert. Raises exactly as
        ``record_verdict`` documents.
        """
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

    def _apply_verdict_submission(
        self,
        project_id: str,
        submission_id: str,
        payload: Mapping[str, object],
        recorded_at: str,
    ) -> str | None:
        """The inbox ``verdict`` effect, inside ``apply_submission``'s transaction.

        Runs the same checks as ``record_verdict``, but returns the reason as a
        rejection instead of raising. The submission id becomes the record id.
        """
        verdict = verdict_from_payload(submission_id, payload)
        rejection = self._verdict_rejection(project_id, verdict)
        if rejection is not None:
            return rejection.reason
        self._insert_verdict(project_id, verdict, recorded_at)
        return None

    def _observation_rows(self, verdict_id: str) -> list[FindingObservation]:
        rows = self._execute(sql_evidence.SELECT_OBSERVATIONS, (verdict_id,))
        return [map_observation(row) for row in rows.fetchall()]

    def _record_from_row(self, row: Sequence[object]) -> VerdictRecord:
        """Map a verdict row and attach its findings, as the reviewer gave them."""
        record = map_verdict(row, ())
        findings = tuple(
            observation_as_finding(observation)
            for observation in self._observation_rows(record.id)
        )
        return dataclasses.replace(record, findings=findings)

    def _load_verdict(self, verdict_id: str) -> VerdictRecord | None:
        row = self._execute(sql_evidence.SELECT_VERDICT_BY_ID, (verdict_id,)).fetchone()
        return None if row is None else self._record_from_row(row)
