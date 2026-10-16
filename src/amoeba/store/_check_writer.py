"""The store's one internal check writer.

Every check is checked and written here — by ``record_check`` and by the inbox's
``check`` effect alike — so both paths run the same checks. As in
``_verdict_writer.py``, the check returns a reason rather than raising: a direct
call raises on it, and the inbox records it as a rejection. The insert never
commits; it runs inside the caller's transaction.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from amoeba.store import sql_checks
from amoeba.store._base import StoreBase, isoformat, now
from amoeba.store.check_models import CheckInput, CheckRecord, check_from_payload
from amoeba.store.models import NodeNotFoundError, StoreIntegrityError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckRejection:
    """Why a check cannot be recorded. ``node_missing`` selects the error type."""

    reason: str
    node_missing: bool = False


_INPUT_FIELDS = tuple(field.name for field in dataclasses.fields(CheckInput))


def _as_input(record: CheckRecord) -> CheckInput:
    return CheckInput(**{name: getattr(record, name) for name in _INPUT_FIELDS})


class CheckWriter(StoreBase):
    """Checks and writes one check result. Never commits."""

    def _check_rejection(
        self, project_id: str, check: CheckInput
    ) -> CheckRejection | None:
        """Every check after the retry rule, in order; ``None`` passes."""
        node = self.get_node(check.node_id)
        if node is None or node.project_id != project_id:
            return CheckRejection(
                f"no node {check.node_id!r} in project {project_id!r}",
                node_missing=True,
            )
        if check.examined_count is not None and check.examined_count < 0:
            return CheckRejection(
                f"examined_count must not be negative: {check.examined_count}"
            )
        if not check.provenance.upstream_version.strip():
            return CheckRejection("upstream_version must not be empty")
        return None

    def _insert_check(
        self, project_id: str, check: CheckInput, recorded_at: str
    ) -> None:
        self._execute(
            sql_checks.INSERT_CHECK,
            sql_checks.check_parameters(check, project_id, recorded_at),
        )

    def _apply_check_submission(
        self,
        project_id: str,
        submission_id: str,
        payload: Mapping[str, object],
        recorded_at: str,
    ) -> str | None:
        """The inbox ``check`` effect, inside ``apply_submission``'s transaction.

        Runs the same checks as ``record_check``, but returns the reason as a
        rejection instead of raising. The submission id becomes the record id.
        """
        check = check_from_payload(submission_id, payload)
        rejection = self._check_rejection(project_id, check)
        if rejection is not None:
            return rejection.reason
        self._insert_check(project_id, check, recorded_at)
        return None

    def _load_check(self, check_id: str) -> CheckRecord | None:
        row = self._execute(sql_checks.SELECT_CHECK_BY_ID, (check_id,)).fetchone()
        return None if row is None else sql_checks.map_check(row)

    def _record_check_within(self, check: CheckInput, project_id: str) -> CheckRecord:
        """``record_check``'s body, inside a transaction the caller opened.

        The retry rule, then the checks, then the insert. Raises exactly as
        ``record_check`` documents.
        """
        existing = self._load_check(check.id)
        if existing is not None:
            if existing.project_id != project_id or _as_input(existing) != check:
                logger.warning(
                    "check %r is already recorded with different content; "
                    "keeping the first",
                    check.id,
                )
            return existing

        rejection = self._check_rejection(project_id, check)
        if rejection is not None:
            if rejection.node_missing:
                raise NodeNotFoundError(rejection.reason)
            raise ValueError(rejection.reason)

        self._insert_check(project_id, check, isoformat(now()))
        recorded = self._load_check(check.id)
        if recorded is None:
            raise StoreIntegrityError(f"check {check.id!r} vanished after insert")
        return recorded
