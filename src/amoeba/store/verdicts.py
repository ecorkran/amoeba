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

from amoeba.store import sql_evidence, sql_inbox
from amoeba.store._base import isoformat, now
from amoeba.store._verdict_writer import VerdictWriter
from amoeba.store.evidence_models import (
    COMPARABLE_STANDINGS,
    FindingChange,
    FindingChanges,
    FindingObservation,
    FindingSummary,
    TaggedFinding,
    VerdictInput,
    VerdictRecord,
)
from amoeba.store.mapping_evidence import map_observation, map_verdict
from amoeba.store.models import (
    NodeNotFoundError,
    StoreIntegrityError,
    VerdictNotFoundError,
)

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

    def verdict(self, verdict_id: str) -> VerdictRecord | None:
        """Return the verdict with this id, or ``None`` if there is none."""
        return self._load_verdict(verdict_id)

    def verdicts(
        self, project_id: str, *, node_id: str | None = None
    ) -> list[VerdictRecord]:
        """A project's verdicts, optionally for one node, in arrival order."""
        statement, parameters = (
            (sql_evidence.SELECT_VERDICTS, (project_id,))
            if node_id is None
            else (sql_evidence.SELECT_VERDICTS_FOR_NODE, (project_id, node_id))
        )
        rows = self._execute(statement, parameters).fetchall()
        return [self._record_from_row(row) for row in rows]

    def observations(self, verdict_id: str) -> list[FindingObservation]:
        """One review's findings as stored, in the order the reviewer gave them.

        Raises:
            VerdictNotFoundError: If no verdict has this id. An empty list would
                look like a real review with no findings.
        """
        self._require_verdict(verdict_id)
        return self._observation_rows(verdict_id)

    def findings(
        self, project_id: str, *, node_id: str | None = None
    ) -> list[FindingSummary]:
        """One row per content key per node, in order of first appearance.

        Each row carries the latest severity, summary, and location, the first
        and last reviews that reported the key, and how many reviews did.
        """
        statement, parameters = (
            (sql_evidence.SELECT_PROJECT_OBSERVATIONS, (project_id,))
            if node_id is None
            else (sql_evidence.SELECT_NODE_OBSERVATIONS, (project_id, node_id))
        )
        folded: dict[tuple[str, int, str], _KeyHistory] = {}
        for row in self._execute(statement, parameters).fetchall():
            node, observation = str(row[0]), map_observation(row[1:])
            key = (node, observation.identity_version, observation.identity)
            folded.setdefault(key, _KeyHistory(node, observation)).see(observation)
        return [history.summary() for history in folded.values()]

    def finding_changes(self, verdict_id: str) -> FindingChanges:
        """What changed in this review since the previous comparable round.

        Worked out now, never stored. The previous round is the latest earlier
        verdict on the same node and review type whose standing is comparable;
        failed rounds are skipped, so they never report open findings as gone.

        Raises:
            VerdictNotFoundError: If no verdict has this id.
        """
        target = self._require_verdict(verdict_id)
        if target.standing not in COMPARABLE_STANDINGS:
            return FindingChanges(
                verdict_id=verdict_id,
                comparable=False,
                previous_verdict_id=None,
                findings=(),
                gone=(),
            )
        current = self._observation_rows(verdict_id)
        previous = self._previous_round(target)
        earlier = [] if previous is None else self._observation_rows(previous.id)
        earlier_keys = {_key(o) for o in earlier}
        current_keys = {_key(o) for o in current}
        gone: dict[tuple[int, str], FindingObservation] = {}
        for observation in earlier:
            if _key(observation) not in current_keys:
                gone.setdefault(_key(observation), observation)
        return FindingChanges(
            verdict_id=verdict_id,
            comparable=True,
            previous_verdict_id=None if previous is None else previous.id,
            findings=tuple(
                TaggedFinding(
                    observation=o,
                    change=(
                        FindingChange.RECURRING
                        if _key(o) in earlier_keys
                        else FindingChange.NEW
                    ),
                )
                for o in current
            ),
            gone=tuple(gone.values()),
        )

    def _previous_round(self, target: VerdictRecord) -> VerdictRecord | None:
        rows = self._execute(
            sql_evidence.SELECT_EARLIER_ROUNDS,
            (
                target.project_id,
                target.node_id,
                target.review_type,
                target.recorded_seq,
            ),
        ).fetchall()
        for row in rows:
            candidate = map_verdict(row, ())
            if candidate.standing in COMPARABLE_STANDINGS:
                return candidate
        return None

    def _require_verdict(self, verdict_id: str) -> VerdictRecord:
        record = self._load_verdict(verdict_id)
        if record is None:
            raise VerdictNotFoundError(f"no verdict with id {verdict_id!r}")
        return record


def _key(observation: FindingObservation) -> tuple[int, str]:
    """Keys compare only within one rule version."""
    return (observation.identity_version, observation.identity)


class _KeyHistory:
    """Folds one key's observations, in arrival order, into a summary row."""

    def __init__(self, node_id: str, first: FindingObservation) -> None:
        self._node_id = node_id
        self._first = first
        self._latest = first
        self._verdict_ids: list[str] = []

    def see(self, observation: FindingObservation) -> None:
        self._latest = observation
        if observation.verdict_id not in self._verdict_ids:
            self._verdict_ids.append(observation.verdict_id)

    def summary(self) -> FindingSummary:
        return FindingSummary(
            node_id=self._node_id,
            identity=self._first.identity,
            identity_version=self._first.identity_version,
            latest_severity=self._latest.severity,
            latest_summary=self._latest.summary,
            latest_location=self._latest.location,
            first_verdict_id=self._first.verdict_id,
            last_verdict_id=self._latest.verdict_id,
            times_seen=len(self._verdict_ids),
        )
