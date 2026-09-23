"""Command journal operations: issue, resolve, escalate, and the two reads.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

The journal's whole purpose is the ordering guarantee in :meth:`issue
<JournalOperations.journal_issue>`: the entry is committed *before* the caller
issues the side effect. A crash in the window between them leaves a durable
unresolved entry, which is what lets recovery ask the external system what
actually happened instead of guessing or re-issuing.

Parameters are validated at issue time rather than at recovery time. Discovering
at 3 a.m., after a crash, that an entry cannot be reconciled because a matching
field was never written is the failure that ordering prevents.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from amoeba.store import sql_journal
from amoeba.store._base import isoformat, new_id, now
from amoeba.store._block_writer import BlockWriter
from amoeba.store.journal_models import (
    REQUIRED_PARAMETER_KEYS,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
)
from amoeba.store.mapping_journal import decode_mapping, map_journal_entry
from amoeba.store.models import (
    BLOCKED_STATUSES,
    BlockedKind,
    InvalidTransitionError,
)

#: Result key carrying the adopted Squadron run id. Defined once here because
#: both the observer that writes it and the matcher that reads it back need the
#: same name.
RESULT_KEY_RUN_ID = "run_id"


class JournalOperations(BlockWriter):
    """The command journal: issue before the side effect, resolve after it."""

    def journal_issue(
        self,
        node_id: str,
        *,
        kind: CommandKind,
        parameters: Mapping[str, object],
    ) -> JournalEntry:
        """Record a command as in flight, and commit before returning.

        Call this *before* issuing the side effect. The commit is the point of
        the method: a crash immediately after it leaves a durable unresolved
        entry, which recovery reconciles by observation.

        Args:
            node_id: The node the command acts on.
            kind: Which command is being issued.
            parameters: What it was issued with. Must carry every key
                :data:`REQUIRED_PARAMETER_KEYS` names for ``kind``; additional
                keys are stored and returned unchanged. Stored verbatim and
                shown by ``amoeba inspect``, so no secrets belong here.

        Returns:
            The committed, unresolved entry.

        Raises:
            NodeNotFoundError: If the node does not exist. Nothing is written.
            ValueError: If a required parameter key for ``kind`` is missing.
                Raised before any write, so the table is left untouched.
        """
        missing = REQUIRED_PARAMETER_KEYS[kind] - set(parameters)
        if missing:
            raise ValueError(
                f"{kind.value} requires parameter keys {sorted(missing)}; "
                f"got {sorted(parameters)}"
            )

        node = self._require_node(node_id)

        issued = now()
        entry = JournalEntry(
            id=new_id(),
            project_id=node.project_id,
            node_id=node_id,
            kind=kind,
            parameters=dict(parameters),
            issued_at=issued,
        )

        with self._connection:
            self._execute(
                sql_journal.INSERT_JOURNAL_ENTRY,
                (
                    entry.id,
                    entry.project_id,
                    entry.node_id,
                    entry.kind.value,
                    json.dumps(entry.parameters),
                    isoformat(issued),
                ),
            )

        return entry

    def journal_resolve(
        self,
        entry_id: str,
        *,
        outcome: JournalOutcome,
        result: Mapping[str, object] | None = None,
        resolved_by: JournalResolver = JournalResolver.ISSUER,
    ) -> JournalEntry:
        """Close an entry with what actually happened.

        Args:
            entry_id: The entry to close.
            outcome: How it ended.
            result: What it produced, stored verbatim. No secrets belong here.
            resolved_by: Who is closing it. Recovery passes
                :attr:`JournalResolver.RECOVERY`; the default is the issuer.

        Returns:
            The closed entry.

        Raises:
            InvalidTransitionError: If the entry does not exist or is already
                resolved. A first outcome is never silently overwritten.
        """
        timestamp = isoformat(now())

        with self._connection:
            cursor = self._execute(
                sql_journal.RESOLVE_JOURNAL_ENTRY,
                (
                    outcome.value,
                    None if result is None else json.dumps(dict(result)),
                    timestamp,
                    resolved_by.value,
                    entry_id,
                ),
            )
            if cursor.rowcount != 1:
                raise InvalidTransitionError(
                    f"journal entry {entry_id!r} does not exist or is already resolved"
                )

        return self._require_entry(entry_id)

    def journal_escalate(self, entry_id: str, *, reason: str) -> JournalEntry:
        """Mark an entry ``unknown`` and block its node on a human.

        One transaction: the outcome and the block land together or neither
        does. This is what recovery calls when it cannot determine whether a
        command reached the external system.

        A node that is *already* blocked is handled as an explicit branch — the
        entry is marked and no second blocked state is written. The node is
        already stopped, and the entry remains visible through
        ``amoeba inspect journal``.

        Args:
            entry_id: The entry to escalate.
            reason: Human-readable explanation, recorded in the blocked-state
                context alongside the entry id.

        Returns:
            The escalated entry.

        Raises:
            InvalidTransitionError: If the entry does not exist or is already
                resolved.
        """
        entry = self._require_entry(entry_id)
        if entry.is_resolved:
            raise InvalidTransitionError(
                f"journal entry {entry_id!r} is already resolved "
                f"({entry.outcome.value if entry.outcome else ''})"
            )

        node = self._require_node(entry.node_id)
        timestamp = isoformat(now())
        # Explicit branch, not a caught InvalidTransitionError: the already-
        # blocked case is an expected state of the world, and catching the
        # error would also swallow a genuine transition bug.
        already_blocked = node.status in BLOCKED_STATUSES

        with self._connection:
            cursor = self._execute(
                sql_journal.RESOLVE_JOURNAL_ENTRY,
                (
                    JournalOutcome.UNKNOWN.value,
                    json.dumps({"reason": reason}),
                    timestamp,
                    JournalResolver.RECOVERY.value,
                    entry_id,
                ),
            )
            if cursor.rowcount != 1:
                raise InvalidTransitionError(
                    f"journal entry {entry_id!r} does not exist or is already resolved"
                )

            if not already_blocked:
                # Through the one block writer, inside this transaction, so the
                # block and the outcome cannot land separately.
                self._write_block(
                    entry.node_id,
                    kind=BlockedKind.HUMAN,
                    context=f"journal entry {entry.id} ({entry.kind.value}): {reason}",
                    timestamp=timestamp,
                )

        return self._require_entry(entry_id)

    def _require_entry(self, entry_id: str) -> JournalEntry:
        """Return an entry, raising when it does not exist."""
        row = self._execute(
            sql_journal.SELECT_JOURNAL_ENTRY_BY_ID, (entry_id,)
        ).fetchone()
        if row is None:
            raise InvalidTransitionError(f"no journal entry with id {entry_id!r}")
        return map_journal_entry(row)

    def journal_entry(self, entry_id: str) -> JournalEntry | None:
        """Return one entry by id, or ``None`` if there is none."""
        row = self._execute(
            sql_journal.SELECT_JOURNAL_ENTRY_BY_ID, (entry_id,)
        ).fetchone()
        return None if row is None else map_journal_entry(row)

    def unresolved_journal_entries(self, project_id: str) -> list[JournalEntry]:
        """Entries still in flight for a project, oldest first.

        What recovery consumes. Served by the partial index on
        ``(project_id, issued_at) WHERE outcome IS NULL``.
        """
        rows = self._execute(
            sql_journal.SELECT_UNRESOLVED_JOURNAL_ENTRIES, (project_id,)
        ).fetchall()
        return [map_journal_entry(row) for row in rows]

    def journal_entries(
        self,
        project_id: str,
        *,
        node_id: str | None = None,
        include_resolved: bool = True,
    ) -> list[JournalEntry]:
        """Entries for a project, oldest first. What inspection consumes.

        Args:
            project_id: The project scope key.
            node_id: Restrict to one node's entries when given.
            include_resolved: When false, only entries still in flight.

        Returns:
            The matching entries, oldest first.
        """
        statement = sql_journal.select_journal_entries(
            by_node=node_id is not None, include_resolved=include_resolved
        )
        parameters: list[object] = [project_id]
        if node_id is not None:
            parameters.append(node_id)

        rows = self._execute(statement, parameters).fetchall()
        return [map_journal_entry(row) for row in rows]

    def recorded_result_run_ids(self, project_id: str) -> dict[str, str]:
        """Run ids already recorded in some entry's result, by entry id.

        The Squadron matcher's fourth candidate condition consumes this: a run
        already adopted by another entry is not a candidate for this one.

        Returns:
            A mapping of ``run_id`` to the entry id that recorded it.
        """
        rows = self._execute(
            sql_journal.SELECT_ENTRIES_WITH_RESULT, (project_id,)
        ).fetchall()

        recorded: dict[str, str] = {}
        for row in rows:
            result = decode_mapping(row[1], sql_journal.COL_JOURNAL_RESULT)
            run_id = result.get(RESULT_KEY_RUN_ID)
            if isinstance(run_id, str):
                recorded[run_id] = str(row[0])
        return recorded


__all__ = [
    "RESULT_KEY_RUN_ID",
    "JournalOperations",
    "map_journal_entry",
]
