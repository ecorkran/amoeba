"""What a pause is, decided from the run alone (slice 224, D3; split out in 262).

``PauseClass``, ``ObservedPause`` and ``classify_run_only`` are plain values and a
pure function that read no process, so the hub's ``pause_begin`` and the client both
decide "the run alone" with the same function (262 D4). ``pause_class`` re-exports
them for the callers that already import them from there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from amoeba.operations.pause_models import SkipReason
from amoeba.store.models import QuestionRecord
from amoeba.store.vocabulary import QuestionState
from amoeba.upstream.squadron.checkpoint_kind import (
    CheckpointKind,
    UnknownKind,
    parse_checkpoint_kind,
)


class PauseClass(StrEnum):
    """What a run's pause is, in the D3 table's order."""

    NOT_PAUSED = "not_paused"
    OTHER_CHECKPOINT = "other_checkpoint"
    NO_QUESTION_TEXT = "no_question_text"
    PROMPT_ONLY = "prompt_only"
    UNHANDLED = "unhandled"
    CLAIM_LIVE = "claim_live"
    CLAIM_STALE = "claim_stale"
    WAITING_ON_PM = "waiting_on_pm"
    ANSWERED_UNRESUMED = "answered_unresumed"
    SETTLED = "settled"
    #: The pause's question was closed (228 D3); the run is still paused.
    CLOSED = "closed"
    #: The question is held on a request this repo sent (242 D9).
    WAITING_ON_REQUEST = "waiting_on_request"


@dataclass(frozen=True)
class ObservedPause:
    """What Squadron says about a run, in the terms both callers can give.

    ``sq runs wait`` and ``sq runs list`` report a run differently (an outcome and a
    status string); each caller reduces its report to this.
    """

    #: Whether the run is paused.
    paused: bool
    #: The checkpoint's kind, raw as Squadron printed it.
    kind: str | None
    #: The checkpoint's ``paused_at`` as ``sq runs wait --json`` prints it.
    paused_at: str | None
    question: str | None


def classify_run_only(observed: ObservedPause) -> PauseClass | None:
    """The first three classes, which need nothing but the run; ``None`` if the run
    is a paused agent question with text, whose class depends on the rest."""
    if not observed.paused:
        return PauseClass.NOT_PAUSED
    if parse_checkpoint_kind(observed.kind) is not CheckpointKind.AGENT_QUESTION:
        return PauseClass.OTHER_CHECKPOINT
    if observed.paused_at is None or not (observed.question or "").strip():
        return PauseClass.NO_QUESTION_TEXT
    return None


def run_only_skip(
    pause_class: PauseClass, outcome: str, checkpoint_kind: str | None
) -> tuple[SkipReason, str | None]:
    """The skip for a class decided from the run alone, with its detail. ``outcome`` is
    the run's outcome text and ``checkpoint_kind`` the checkpoint's raw kind."""
    match pause_class:
        case PauseClass.NOT_PAUSED:
            return SkipReason.NOT_PAUSED, f"the run's outcome is {outcome}"
        case PauseClass.OTHER_CHECKPOINT:
            kind = parse_checkpoint_kind(checkpoint_kind)
            return SkipReason.NOT_AGENT_QUESTION, f"checkpoint kind {_raw(kind)}"
        case PauseClass.NO_QUESTION_TEXT:
            return SkipReason.NO_QUESTION_TEXT, None
        case _:
            raise ValueError(f"{pause_class} is not decided from the run alone")


def _raw(kind: CheckpointKind | UnknownKind | None) -> str:
    if kind is None:
        return "not reported"
    return kind.raw if isinstance(kind, UnknownKind) else kind.value


def claim_is_stale(row: QuestionRecord, now: datetime, limit_seconds: float) -> bool:
    """Whether the row is a claim whose last write (``updated_at``) is at least
    ``limit_seconds`` old: ``pause_claim_seconds``, judged on the caller's clock (the
    hub's, in ``pause_begin`` and ``status``)."""
    return row.state is QuestionState.CLAIMED and now - row.updated_at >= timedelta(
        seconds=limit_seconds
    )
