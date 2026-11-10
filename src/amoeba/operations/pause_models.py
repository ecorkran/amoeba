"""The result values of the pause operations (slice 223, D3, D8, D13)."""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.store.vocabulary import ResumeOutcome


@dataclass(frozen=True)
class ResumeResult:
    """What handing an answer back to the paused run came to (D8)."""

    outcome: ResumeOutcome
    #: Why it was refused or not delivered; ``None`` for a resume that took.
    detail: str | None
    #: Path of the resume's stdout log, when a child was started.
    resume_log: str | None
