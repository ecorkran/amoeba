"""Applying a submission, and reading the record of what was applied.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

``apply_submission`` is **one transaction**: replay check, precondition,
effect, record. The effect and the record commit together or neither does, so
no state exists where a slot is filled but the submission is unrecorded, or
the reverse. The replay check makes the effect exactly-once per submission id
(D2); the record's ``applied_seq`` is the receiver-assigned order (D4).

**Rejection is a recorded outcome, not an exception.** Each precondition is an
explicit branch returning a reason. ``InvalidTransitionError`` is never caught
to implement one — that would also swallow a genuine bug. An effect *raises*
only when its input is malformed, which the envelope validation upstream
should have made impossible.

``amoeba.store`` never imports ``amoeba.inbox``: the values arriving here are
plain and already validated. The payload keys each effect reads are defined
once, in ``inbox_models``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from amoeba.store import sql, sql_inbox
from amoeba.store._base import isoformat, new_id, now
from amoeba.store._block_writer import BlockWriter
from amoeba.store._verdict_writer import VerdictWriter
from amoeba.store.inbox_models import (
    INTENT_BODY,
    INTENT_NODE_ID,
    RESOLUTION_BLOCKED_STATE_ID,
    RESOLUTION_DETAIL,
    Channel,
    SubmissionKind,
    SubmissionOutcome,
    SubmissionRecord,
)
from amoeba.store.mapping import map_blocked_state
from amoeba.store.mapping_inbox import map_submission_record
from amoeba.store.models import StoreIntegrityError


@dataclass(frozen=True)
class _Application:
    """What an effect needs: one submission, inside the apply transaction."""

    project_id: str
    submission_id: str
    submitted_by: str
    payload: Mapping[str, object]
    timestamp: str


#: An effect applies one kind. ``None`` means applied; a string is the reason
#: the submission was rejected.
type Effect = Callable[[InboxOperations, _Application], str | None]


def _payload_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"submission payload {key!r} must be a string: {value!r}")
    return value


def _payload_optional_text(payload: Mapping[str, object], key: str) -> str | None:
    return None if payload.get(key) is None else _payload_text(payload, key)


def _payload_mapping(payload: Mapping[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"submission payload {key!r} must be an object: {value!r}")

    # Narrowed key by key, as ``decode_mapping`` does: the isinstance check
    # above cannot type the contents.
    narrowed: dict[str, object] = {}
    for item_key, item in value.items():  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item_key, str):
            raise ValueError(f"submission payload {key!r} has a non-string key")
        narrowed[item_key] = item
    return narrowed


class InboxOperations(BlockWriter, VerdictWriter):
    """Apply a submission exactly once, and read back what was applied."""

    def apply_submission(
        self,
        *,
        submission_id: str,
        project_id: str,
        kind: SubmissionKind,
        submitted_by: str,
        submitted_at: datetime,
        payload: Mapping[str, object],
    ) -> SubmissionRecord:
        """Apply one submission in one transaction.

        Args:
            submission_id: The submitter's id — the idempotency key.
            project_id: The project the submission is for. Recorded, and the
                scope every precondition checks against.
            kind: What the submission asks for.
            submitted_by: Free-form provenance. Never branched on.
            submitted_at: The submitter's clock. Recorded, never used to order.
            payload: Already-validated values for ``kind``.

        Returns:
            The record: new, or — on replay — the existing one, unchanged.

        Raises:
            ValueError: If ``payload`` is malformed for ``kind``. Nothing is
                written.
        """
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            if (existing := self.submission(submission_id)) is not None:
                return existing

            timestamp = isoformat(now())
            reason = self.KIND_EFFECTS[kind](
                self,
                _Application(
                    project_id=project_id,
                    submission_id=submission_id,
                    submitted_by=submitted_by,
                    payload=payload,
                    timestamp=timestamp,
                ),
            )
            outcome = (
                SubmissionOutcome.APPLIED
                if reason is None
                else SubmissionOutcome.REJECTED
            )
            self._execute(
                sql_inbox.INSERT_SUBMISSION,
                (
                    submission_id,
                    project_id,
                    kind.value,
                    submitted_by,
                    isoformat(submitted_at),
                    json.dumps(dict(payload)),
                    outcome.value,
                    reason,
                    timestamp,
                ),
            )

        record = self.submission(submission_id)
        if record is None:
            raise StoreIntegrityError(f"submission {submission_id!r} was not recorded")
        return record

    def submission(self, submission_id: str) -> SubmissionRecord | None:
        """One record, or ``None`` if the submission has not been applied."""
        row = self._execute(
            sql_inbox.SELECT_SUBMISSION_BY_ID, (submission_id,)
        ).fetchone()
        return None if row is None else map_submission_record(row)

    def submissions(
        self, project_id: str, *, outcome: SubmissionOutcome | None = None
    ) -> list[SubmissionRecord]:
        """Every record for a project, in ``applied_seq`` order."""
        if outcome is None:
            rows = self._execute(sql_inbox.SELECT_SUBMISSIONS, (project_id,))
        else:
            rows = self._execute(
                sql_inbox.SELECT_SUBMISSIONS_BY_OUTCOME, (project_id, outcome.value)
            )
        return [map_submission_record(row) for row in rows.fetchall()]

    # ----------------------------------------------------------------------
    # Effects — one per kind, each inside the apply transaction
    # ----------------------------------------------------------------------

    # Each effect annotates ``self`` as ``InboxOperations`` rather than leaving
    # it inferred as ``Self``, so the functions fit the ``Effect`` type of the
    # table below.

    def _apply_create_project(
        self: InboxOperations, application: _Application
    ) -> str | None:
        """No precondition, no row: the store existing *is* the effect.

        The tenant has already created-or-opened it. A project that already
        existed is ``applied`` too — the requested state holds.
        """
        del application
        return None

    def _apply_resolution(
        self: InboxOperations, application: _Application
    ) -> str | None:
        """Fill the targeted blocked state's slot, if it is still the open one."""
        blocked_state_id = _payload_text(
            application.payload, RESOLUTION_BLOCKED_STATE_ID
        )
        detail = _payload_text(application.payload, RESOLUTION_DETAIL)

        row = self._execute(
            sql.SELECT_BLOCKED_STATE_BY_ID, (blocked_state_id,)
        ).fetchone()
        if row is None:
            return f"blocked state {blocked_state_id!r} does not exist"
        state = map_blocked_state(row)

        node = self.get_node(state.node_id)
        if node is None or node.project_id != application.project_id:
            return f"blocked state {blocked_state_id!r} is not in this project"
        if state.is_resolved:
            # Also the stale-reply case: a node re-blocked since this block was
            # raised has resolved it, so the reply is never redirected.
            return f"blocked state {blocked_state_id!r} is already resolved"

        # Unresolved, and the one-open-block-per-node index makes it the
        # node's open one — so the slot must fill.
        if not self._write_resolution(
            state.node_id,
            resolved_by=application.submitted_by,
            detail=detail,
            timestamp=application.timestamp,
        ):
            raise StoreIntegrityError(
                f"blocked state {blocked_state_id!r} is open but its slot "
                "could not be filled"
            )
        return None

    def _apply_intent(self: InboxOperations, application: _Application) -> str | None:
        """Write one unacknowledged ``intent`` row carrying the submission id."""
        node_id = _payload_optional_text(application.payload, INTENT_NODE_ID)
        body = _payload_mapping(application.payload, INTENT_BODY)

        if node_id is not None:
            node = self.get_node(node_id)
            if node is None or node.project_id != application.project_id:
                return f"node {node_id!r} does not exist in this project"

        self._execute(
            sql_inbox.INSERT_MESSAGE,
            (
                new_id(),
                application.project_id,
                Channel.INTENT.value,
                node_id,
                None,
                None,
                application.submission_id,
                json.dumps(body),
                application.timestamp,
            ),
        )
        return None

    def _apply_verdict(self: InboxOperations, application: _Application) -> str | None:
        """Record a review; the checks and insert live beside ``record_verdict``."""
        return self._apply_verdict_submission(
            application.project_id,
            application.submission_id,
            application.payload,
            application.timestamp,
        )

    #: The kind-to-effect table, defined once. A kind missing here fails a
    #: test, not a user.
    KIND_EFFECTS: ClassVar[Mapping[SubmissionKind, Effect]] = {
        SubmissionKind.CREATE_PROJECT: _apply_create_project,
        SubmissionKind.RESOLUTION: _apply_resolution,
        SubmissionKind.INTENT: _apply_intent,
        SubmissionKind.VERDICT: _apply_verdict,
    }
