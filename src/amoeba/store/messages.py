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
from amoeba.store.inbox_models import Channel, Message
from amoeba.store.mapping_inbox import map_message
from amoeba.store.models import InvalidTransitionError


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

    def acknowledge_message(self, message_id: str, *, acknowledged_by: str) -> Message:
        """Mark an ``intent`` row consumed.

        Args:
            message_id: The intent to acknowledge.
            acknowledged_by: Who consumed it. Free-form; never branched on.

        Returns:
            The acknowledged message.

        Raises:
            InvalidTransitionError: If the row does not exist, is not an intent,
                or is already acknowledged. A first acknowledgement is never
                silently overwritten.
        """
        with self._connection:
            cursor = self._execute(
                sql_inbox.ACKNOWLEDGE_MESSAGE,
                (
                    isoformat(now()),
                    acknowledged_by,
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
