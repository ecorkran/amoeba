"""What a sweep closed, as ``status`` reports it in ``closed_now`` (slice 228, D12)."""

from __future__ import annotations

from collections.abc import Mapping

from amoeba.operations.decisions_models import MemberName
from amoeba.operations.question_sweep import SweepResult
from amoeba.operations.status_models import ClosedNowEntry


def closed_now_entries(
    swept: SweepResult,
    program_of: Mapping[str, str],
    names: Mapping[str, str],
) -> tuple[ClosedNowEntry, ...]:
    """One entry per question closed and per answer marked ``not_delivered``.

    ``program_of`` and ``names`` map a member's project id to its program and name.
    """
    closed = tuple(
        ClosedNowEntry(
            program=program_of[item.member_id],
            member=MemberName(id=item.member_id, name=names[item.member_id]),
            run_id=item.key.run_id,
            paused_at=item.key.paused_at,
            question=item.question,
            closed_reason=item.closed_reason,
            closed_detail=item.closed_detail,
        )
        for item in swept.closed
    )
    undelivered = tuple(
        ClosedNowEntry(
            program=program_of[item.member_id],
            member=MemberName(id=item.member_id, name=names[item.member_id]),
            run_id=item.key.run_id,
            paused_at=item.key.paused_at,
            question=item.question,
            closed_reason=None,
            closed_detail=item.detail,
            answer_seq=item.answer_seq,
            resume_outcome=item.resume_outcome,
        )
        for item in swept.undelivered
    )
    return closed + undelivered
