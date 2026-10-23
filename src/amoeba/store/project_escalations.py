"""Project-scoped escalations: a fault that has no node (D4).

Mixed into ``Store``; see ``store.py`` for the assembled public class.

A project-scoped escalation is an ``escalation`` message with a ``fault_kind``
and no node or blocked state. The schema allows at most one open row per
``(project, fault kind)``, so a fault that recurs every tick cannot storm. Only
the Runner closes one. ``fault_kind``'s vocabulary belongs to the Runner; the
store holds it as text. Payloads are stored verbatim and shown by inspection, so
callers must not place secrets in them.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from amoeba.store import sql_runner
from amoeba.store._base import StoreBase, isoformat, new_id, now
from amoeba.store.inbox_models import Channel, Message
from amoeba.store.mapping_inbox import map_message
from amoeba.store.models import InvalidTransitionError


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must be non-empty text")


def _encode_payload(payload: Mapping[str, object]) -> str:
    try:
        return json.dumps(dict(payload))
    except TypeError as error:
        # Specific: a payload that is not JSON-serializable is a caller error,
        # reported as the ValueError every malformed write raises.
        raise ValueError(f"payload is not JSON-serializable: {error}") from error


class ProjectEscalationOperations(StoreBase):
    """Raise, list and close project-scoped escalations."""

    def raise_project_escalation(
        self, project_id: str, *, fault_kind: str, payload: Mapping[str, object]
    ) -> Message:
        """Open an escalation for a fault, or return the one already open.

        If a row is open for ``(project_id, fault_kind)`` it is returned
        unchanged and nothing is written. Otherwise a row is inserted, and the
        existing ``message_posted`` trigger puts it on the change feed.

        Args:
            project_id: The project the fault belongs to.
            fault_kind: What kind of fault. Non-empty; its vocabulary is the
                Runner's.
            payload: The opaque mapping describing the fault. Required.

        Raises:
            ValueError: If ``fault_kind`` is empty or ``payload`` is not
                JSON-serializable. Nothing is written.
        """
        _require_text(fault_kind, "fault_kind")
        encoded = _encode_payload(payload)

        existing = self._execute(
            sql_runner.SELECT_OPEN_PROJECT_ESCALATION, (project_id, fault_kind)
        ).fetchone()
        if existing is not None:
            return map_message(existing)

        message_id = new_id()
        with self._connection:
            self._execute(
                sql_runner.INSERT_PROJECT_ESCALATION,
                (
                    message_id,
                    project_id,
                    Channel.ESCALATION.value,
                    None,
                    None,
                    None,
                    None,
                    encoded,
                    isoformat(now()),
                    fault_kind,
                ),
            )
        return self._require_message(message_id)

    def open_project_escalations(self, project_id: str) -> list[Message]:
        """Open project-scoped escalations for a project, in ``seq`` order."""
        rows = self._execute(
            sql_runner.SELECT_OPEN_PROJECT_ESCALATIONS, (project_id,)
        ).fetchall()
        return [map_message(row) for row in rows]

    def close_project_escalation(self, message_id: str, *, closed_by: str) -> Message:
        """Record that the Runner closed a project-scoped escalation.

        A later fault of the same kind then opens a new row.

        Raises:
            ValueError: If ``closed_by`` is empty.
            InvalidTransitionError: If the row does not exist, is not a
                project-scoped escalation, or is already closed.
        """
        _require_text(closed_by, "closed_by")

        with self._connection:
            cursor = self._execute(
                sql_runner.CLOSE_PROJECT_ESCALATION,
                (isoformat(now()), closed_by, message_id),
            )
            if cursor.rowcount != 1:
                raise InvalidTransitionError(
                    f"message {message_id!r} does not exist, is not an open "
                    "project-scoped escalation, or is already closed"
                )
        return self._require_message(message_id)
