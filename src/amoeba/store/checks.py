"""Recording check results and progress records, and reading checks back.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

``record_check`` is one transaction: the retry check, the checks, and the insert
commit together or not at all. The caller supplies the id, so recording again
after a crash is harmless: the first record wins, and a WARNING says so if the
content differs. ``record_progress`` is a bare insert (D6): progress records are
write-only until a consumer defines their fields.
"""

from __future__ import annotations

from amoeba.store import sql_checks, sql_inbox
from amoeba.store._base import isoformat, now
from amoeba.store._check_writer import CheckWriter
from amoeba.store.check_models import CheckInput, CheckRecord, ProgressInput
from amoeba.store.models import StoreIntegrityError


class CheckOperations(CheckWriter):
    """Record checks and progress records; read checks back."""

    def record_check(self, check: CheckInput, *, project_id: str) -> CheckRecord:
        """Record one check result in one transaction.

        Args:
            check: The result. Its ``id`` is the retry key.
            project_id: The project the check belongs to; the node must be in it.

        Returns:
            The new record or, when the id is already recorded, the existing one.

        Raises:
            NodeNotFoundError: If the node does not exist in ``project_id``.
            ValueError: If ``examined_count`` is negative or ``upstream_version``
                is empty. Nothing is written.
        """
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            return self._record_check_within(check, project_id)

    def check(self, check_id: str) -> CheckRecord | None:
        """Return the check with this id, or ``None`` if there is none."""
        return self._load_check(check_id)

    def checks(
        self, project_id: str, *, node_id: str | None = None
    ) -> list[CheckRecord]:
        """A project's checks, optionally for one node, in arrival order."""
        statement, parameters = (
            (sql_checks.SELECT_CHECKS, (project_id,))
            if node_id is None
            else (sql_checks.SELECT_CHECKS_FOR_NODE, (project_id, node_id))
        )
        return [
            sql_checks.map_check(row)
            for row in self._execute(statement, parameters).fetchall()
        ]

    def record_progress(self, progress: ProgressInput, *, project_id: str) -> None:
        """Insert one progress record. No retry rule and no content checks (D6).

        The one check is that the node is in ``project_id``: the table's foreign
        key sees only the node, so a mismatch would silently mis-attribute it.

        Raises:
            StoreIntegrityError: If the node is missing or in another project,
                or the id is already recorded.
        """
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            node = self.get_node(progress.node_id)
            if node is None or node.project_id != project_id:
                raise StoreIntegrityError(
                    f"no node {progress.node_id!r} in project {project_id!r}"
                )
            self._execute(
                sql_checks.INSERT_PROGRESS,
                sql_checks.progress_parameters(progress, project_id, isoformat(now())),
            )
