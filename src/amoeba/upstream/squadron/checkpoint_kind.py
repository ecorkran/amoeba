"""A checkpoint's kind and the verbatim kind Squadron reports that this code has no
member for (slice 132; split out in slice 262).

Plain values and no process: the hub imports this module (through ``classify_run_only``)
without reaching the code that runs ``sq``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CheckpointKind(StrEnum):
    """Why a run paused, as Squadron names it (observed squadron-ai 0.23.5)."""

    LOOP_EXHAUSTED = "loop_exhausted"
    INTERACTIVE_CHECKPOINT = "interactive_checkpoint"
    AWAITS_HUMAN = "awaits_human"
    #: squadron#248: a pause for a usage limit. Its round never ran, so accept is
    #: refused and the answer is retry after ``resets_at`` (slice 127, D2).
    USAGE_LIMIT = "usage_limit"
    #: squadron#249: the agent ended on a question instead of an artifact. The
    #: answer is a resume carrying instructions (slice 132, D10).
    AGENT_QUESTION = "agent_question"
    OTHER = "other"


@dataclass(frozen=True)
class UnknownKind:
    """A kind Squadron reported that this code has no member for, text unchanged.

    An unrecognized kind never fails a poll and is never mapped to a near match;
    the caller sees the raw text and decides.
    """

    raw: str


def parse_checkpoint_kind(raw: str | None) -> CheckpointKind | UnknownKind | None:
    """A checkpoint's kind: a member, ``UnknownKind(raw)``, or ``None`` if unset."""
    return parse_kind(CheckpointKind, raw)


def parse_kind[KindT: StrEnum](
    members: type[KindT], raw: str | None
) -> KindT | UnknownKind | None:
    if raw is None:
        return None
    try:
        return members(raw)
    except ValueError:
        # Specific: Squadron named a kind newer than this code. An answer, kept
        # verbatim, not a failure.
        return UnknownKind(raw)
