"""Message reads and acknowledgement.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

Messages are **written** in two places only: escalations by the one block writer
(D3), and intents by ``apply_submission``. This module reads them, and marks an
intent consumed. The reads work through a read-only handle, so an outside
consumer needs no write access to follow a channel.
"""

from __future__ import annotations

from amoeba.store import sql_inbox
from amoeba.store._base import StoreBase, isoformat, now
from amoeba.store.inbox_models import AcknowledgmentOutcome, Channel, Message
from amoeba.store.mapping_inbox import map_message
from amoeba.store.models import InvalidTransitionError


def _validated_outcome(
    outcome: AcknowledgmentOutcome, reason: str | None
) -> AcknowledgmentOutcome:
    """Coerce the outcome and check its reason, before anything is written."""
    validated = AcknowledgmentOutcome(outcome)
    if reason is not None and not reason:
        raise ValueError("an acknowledgment reason, when given, must not be empty")
    if validated is AcknowledgmentOutcome.REJECTED and not (reason and reason.strip()):
        raise ValueError("a rejected acknowledgment needs a non-blank reason")
    return validated


class MessageOperations(StoreBase):
    """The replay primitive, the Runner's intent queue, and acknowledgement."""

    def messages(
        self, project_id: str, *, channel: Channel, after_seq: int = 0
    ) -> list[Message]:
        """Rows on one channel with ``seq > after_seq``, ascending.

        The replay primitive: a consumer remembers the last ``seq`` it handled
        and asks for what came after. Stable across repeated calls.
        """
        rows = self._execute(
            sql_inbox.SELECT_MESSAGES_AFTER, (project_id, channel.value, after_seq)
        ).fetchall()
        return [map_message(row) for row in rows]

    def pending_intents(self, project_id: str) -> list[Message]:
        """Unacknowledged ``intent`` rows, ascending. What the Runner consumes."""
        rows = self._execute(sql_inbox.SELECT_PENDING_INTENTS, (project_id,)).fetchall()
        return [map_message(row) for row in rows]

    def acknowledge_message(
        self,
        message_id: str,
        *,
        acknowledged_by: str,
        outcome: AcknowledgmentOutcome,
        reason: str | None = None,
    ) -> Message:
        """Mark an ``intent`` row consumed, and record how it ended.

        A row acknowledged before outcomes were recorded (migration 009) reads
        back with a ``None`` outcome; that means "acknowledged before outcomes
        were recorded".

        Args:
            message_id: The intent to acknowledge.
            acknowledged_by: Who consumed it. Free-form; never branched on.
            outcome: How it ended. Required; there is no default.
            reason: Why. Required, and non-blank, for ``rejected``; optional
                for the other outcomes, and non-empty when given.

        Returns:
            The acknowledged message.

        Raises:
            ValueError: If ``outcome`` is outside the vocabulary, ``rejected``
                has no reason, or a given reason is empty. Nothing is written.
            InvalidTransitionError: If the row does not exist, is not an intent,
                or is already acknowledged. A first acknowledgement is never
                silently overwritten.
        """
        validated = _validated_outcome(outcome, reason)

        with self._connection:
            cursor = self._execute(
                sql_inbox.ACKNOWLEDGE_MESSAGE,
                (
                    isoformat(now()),
                    acknowledged_by,
                    validated.value,
                    reason,
                    message_id,
                    Channel.INTENT.value,
                ),
            )
            if cursor.rowcount != 1:
                raise InvalidTransitionError(
                    f"message {message_id!r} does not exist, is not an intent, "
                    "or is already acknowledged"
                )

        row = self._execute(sql_inbox.SELECT_MESSAGE_BY_ID, (message_id,)).fetchone()
        if row is None:
            raise InvalidTransitionError(f"message {message_id!r} vanished")
        return map_message(row)

    def intent_for_submission(self, submission_id: str) -> Message | None:
        """The intent row a submission created, or ``None`` if there is none.

        After ``submission(id)`` reports ``applied``, this row is either
        unacknowledged (the Runner has not consumed it) or carries its outcome.
        Works through a read-only handle. The lookup scans the intent rows
        (``submission_id`` has no index); see issue #19.
        """
        row = self._execute(
            sql_inbox.SELECT_INTENT_BY_SUBMISSION,
            (submission_id, Channel.INTENT.value),
        ).fetchone()
        return None if row is None else map_message(row)
