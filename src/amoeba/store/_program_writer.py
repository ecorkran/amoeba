"""The program store's one write path: ``apply_submission``.

One ``BEGIN IMMEDIATE`` transaction per submission: a reused id returns the
existing record untouched (first wins); otherwise the kind's checks run against
the stored state, and either its writes happen or nothing but the submission
record does. A rejection is a recorded outcome, never an exception; a failure
inside the transaction rolls everything back, the submission record included.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime

from amoeba.store import sql_inbox, sql_program
from amoeba.store._base import isoformat, now
from amoeba.store._program_reads import ProgramReads
from amoeba.store._program_specs import (
    MemberRegistration,
    MemberSpec,
    ProgramSpec,
    parse_member_registration,
    parse_program,
)
from amoeba.store.inbox_models import SubmissionOutcome
from amoeba.store.models import StoreIntegrityError
from amoeba.store.program_models import (
    Member,
    ProgramRejection,
    ProgramSubmissionKind,
    ProgramSubmissionRecord,
)


def _rejection(code: ProgramRejection, detail: str) -> str:
    """The recorded reason: ``"<code>: <detail>"``. Callers branch on the code."""
    return f"{code.value}: {detail}"


class ProgramWriter(ProgramReads):
    """Applies program submissions, exactly once each."""

    def apply_submission(
        self,
        *,
        submission_id: str,
        kind: ProgramSubmissionKind,
        submitted_by: str,
        submitted_at: datetime,
        payload: Mapping[str, object],
    ) -> ProgramSubmissionRecord:
        """Apply one submission in one transaction.

        Args:
            submission_id: The submitter's id — the idempotency key.
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
            reason = self._apply_kind(kind, payload, timestamp)
            outcome = (
                SubmissionOutcome.APPLIED
                if reason is None
                else SubmissionOutcome.REJECTED
            )
            self._execute(
                sql_program.INSERT_SUBMISSION,
                (
                    submission_id,
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

    def _apply_kind(
        self, kind: ProgramSubmissionKind, payload: Mapping[str, object], timestamp: str
    ) -> str | None:
        """Run the kind's checks and writes. ``None`` is applied, else the reason."""
        match kind:
            case ProgramSubmissionKind.REGISTER_PROGRAM:
                return self._register_program(parse_program(payload), timestamp)
            case ProgramSubmissionKind.REGISTER_MEMBER:
                registration = parse_member_registration(payload)
                return self._register_member(registration, timestamp)

    # ----------------------------------------------------------------------
    # register_program: create, or replace whole
    # ----------------------------------------------------------------------

    def _register_program(self, spec: ProgramSpec, timestamp: str) -> str | None:
        current = {m.project_id: m for m in self.members(spec.program_id)}
        if (reason := self._program_rejection(spec, set(current))) is not None:
            return reason

        existing = self.program(spec.program_id)
        if existing is None:
            self._execute(
                sql_program.INSERT_PROGRAM,
                (
                    spec.program_id,
                    spec.concept_member,
                    spec.concept_path,
                    timestamp,
                    timestamp,
                ),
            )

        kept = {member.project_id for member in spec.members}
        changed = existing is not None and (
            (existing.concept_member, existing.concept_path)
            != (spec.concept_member, spec.concept_path)
        )
        for dropped in current.keys() - kept:
            self._delete_member(spec.program_id, dropped)
            changed = True
        for member in spec.members:
            member_changed = self._write_member(
                spec.program_id, member, current.get(member.project_id), timestamp
            )
            changed = changed or member_changed

        if existing is not None and changed:
            self._execute(
                sql_program.UPDATE_PROGRAM,
                (spec.concept_member, spec.concept_path, timestamp, spec.program_id),
            )
        return None

    def _program_rejection(self, spec: ProgramSpec, current: set[str]) -> str | None:
        """The first failing check, in the documented order, before any write."""
        listed = {member.project_id for member in spec.members}
        for member in spec.members:
            owner = self.program_of(member.project_id)
            if owner is not None and owner.program_id != spec.program_id:
                return _rejection(
                    ProgramRejection.MEMBER_OF_OTHER_PROGRAM,
                    f"{member.project_id} is a member of {owner.program_id}",
                )
        if spec.concept_member not in listed:
            return _rejection(
                ProgramRejection.CONCEPT_MEMBER_NOT_MEMBER,
                f"{spec.concept_member} is not among the listed members",
            )
        if (reason := _override_rejection(spec.members, listed)) is not None:
            return reason
        return self._referenced_rejection(spec.program_id, current - listed)

    def _referenced_rejection(self, program_id: str, dropped: set[str]) -> str | None:
        """Reserved ``member_referenced`` hook: nothing references a member yet.

        Edges (183) and requests (184) add their tables and, each in this same
        transaction, a check that no dropped member is referenced. Until then it
        finds nothing, so it never rejects.
        """
        del program_id, dropped
        return None

    # ----------------------------------------------------------------------
    # register_member: upsert one
    # ----------------------------------------------------------------------

    def _register_member(
        self, registration: MemberRegistration, timestamp: str
    ) -> str | None:
        program_id = registration.program_id
        member = registration.member
        if self.program(program_id) is None:
            return _rejection(
                ProgramRejection.UNKNOWN_PROGRAM, f"no program {program_id}"
            )
        owner = self.program_of(member.project_id)
        if owner is not None and owner.program_id != program_id:
            return _rejection(
                ProgramRejection.MEMBER_OF_OTHER_PROGRAM,
                f"{member.project_id} is a member of {owner.program_id}",
            )
        current = {m.project_id: m for m in self.members(program_id)}
        if (
            reason := _override_rejection((member,), {*current, member.project_id})
        ) is not None:
            return reason

        if self._write_member(
            program_id, member, current.get(member.project_id), timestamp
        ):
            self._execute(sql_program.TOUCH_PROGRAM, (timestamp, program_id))
        return None

    # ----------------------------------------------------------------------
    # Member rows
    # ----------------------------------------------------------------------

    def _write_member(
        self, program_id: str, spec: MemberSpec, existing: Member | None, timestamp: str
    ) -> bool:
        """Insert or update one member and its overrides. Whether anything changed."""
        if existing is None:
            self._execute(
                sql_program.INSERT_MEMBER,
                (
                    program_id,
                    spec.project_id,
                    spec.requests_initiative,
                    spec.consumed.value,
                    timestamp,
                    timestamp,
                ),
            )
        elif (
            existing.requests_initiative == spec.requests_initiative
            and existing.consumed == spec.consumed
            and dict(existing.overrides) == dict(spec.overrides)
        ):
            return False
        else:
            self._execute(
                sql_program.UPDATE_MEMBER,
                (
                    spec.requests_initiative,
                    spec.consumed.value,
                    timestamp,
                    program_id,
                    spec.project_id,
                ),
            )

        self._execute(
            sql_program.DELETE_OVERRIDES_OF_PROVIDER, (program_id, spec.project_id)
        )
        for dependent, mode in sorted(spec.overrides.items()):
            self._execute(
                sql_program.INSERT_OVERRIDE,
                (program_id, spec.project_id, dependent, mode.value),
            )
        return True

    def _delete_member(self, program_id: str, project_id: str) -> None:
        self._execute(
            sql_program.DELETE_OVERRIDES_OF_PROVIDER, (program_id, project_id)
        )
        self._execute(sql_program.DELETE_MEMBER, (program_id, project_id))


def _override_rejection(members: tuple[MemberSpec, ...], valid: set[str]) -> str | None:
    """``override_not_member``: an override names a project that is not a member."""
    for member in members:
        for dependent in sorted(member.overrides):
            if dependent not in valid:
                return _rejection(
                    ProgramRejection.OVERRIDE_NOT_MEMBER,
                    f"{member.project_id} overrides for {dependent}, "
                    "which is not a member",
                )
    return None
