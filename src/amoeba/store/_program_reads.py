"""The program store's reads, shared by ``ProgramStore`` and its writer.

A base of its own so the writer's apply transaction can read the stored state it
checks against without importing ``ProgramStore``.
"""

from __future__ import annotations

from amoeba.store import mapping_program, sql_program
from amoeba.store._base import StatementRunner
from amoeba.store.program_models import (
    ConsumptionMode,
    Member,
    Program,
    ProgramSubmissionRecord,
)


class ProgramReads(StatementRunner):
    """Typed reads over the program store's tables."""

    def programs(self) -> list[Program]:
        """Every program, ordered by id."""
        rows = self._execute(sql_program.SELECT_PROGRAMS, ()).fetchall()
        return [mapping_program.map_program(row) for row in rows]

    def program(self, program_id: str) -> Program | None:
        """One program, or ``None`` if there is none."""
        row = self._execute(sql_program.SELECT_PROGRAM_BY_ID, (program_id,)).fetchone()
        return None if row is None else mapping_program.map_program(row)

    def program_of(self, project_id: str) -> Program | None:
        """The program a project is a member of, or ``None`` (D3: at most one)."""
        row = self._execute(
            sql_program.SELECT_PROGRAM_OF_PROJECT, (project_id,)
        ).fetchone()
        return None if row is None else mapping_program.map_program(row)

    def members(self, program_id: str) -> list[Member]:
        """A program's members, ordered by project id, each with its overrides."""
        overrides: dict[str, dict[str, ConsumptionMode]] = {}
        for row in self._execute(sql_program.SELECT_OVERRIDES, (program_id,)):
            provider, dependent, mode = mapping_program.map_override(row)
            overrides.setdefault(provider, {})[dependent] = mode
        rows = self._execute(sql_program.SELECT_MEMBERS, (program_id,)).fetchall()
        return [
            mapping_program.map_member(row, overrides.get(str(row[1]), {}))
            for row in rows
        ]

    def submission(self, submission_id: str) -> ProgramSubmissionRecord | None:
        """One record, or ``None`` if the submission has not been applied."""
        row = self._execute(
            sql_program.SELECT_SUBMISSION_BY_ID, (submission_id,)
        ).fetchone()
        return None if row is None else mapping_program.map_submission(row)

    def submissions(self) -> list[ProgramSubmissionRecord]:
        """Every applied and rejected submission, in ``applied_seq`` order."""
        rows = self._execute(sql_program.SELECT_SUBMISSIONS, ()).fetchall()
        return [mapping_program.map_submission(row) for row in rows]
