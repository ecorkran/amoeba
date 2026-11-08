"""The answer gate: the one check every answer passes before it is submitted.

Pure: no I/O, no clock, no store. Whatever records the answer calls it while holding
its own write lock, with the question text and the count of answers the answerer
already gave this run, so it must stay cheap and side-effect free (slice 142, D1).
The caller binds the answer and the project's settings with ``functools.partial``
over :func:`evaluate_gate`.
"""

from __future__ import annotations

import re
from typing import Final

from amoeba.answering.settings import AnswererSettings
from amoeba.answering.values import DeclineReason, GateRefusal

_WHITESPACE_RUN: Final = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Casefold and collapse every run of whitespace to one space (D2).

    The one definition of how the reserved screen compares text.
    """
    return _WHITESPACE_RUN.sub(" ", text.casefold())


def evaluate_gate(
    question: str,
    prior_answers: int,
    *,
    answer: str,
    settings: AnswererSettings,
) -> GateRefusal | None:
    """Return why the answer must not be submitted, or ``None`` to let it through.

    The answer limit is checked first, then each reserved term in configured
    order against the question and then the answer. Matching is a substring
    match with no word boundaries, so ``push`` also matches ``pushed``: over-
    matching costs one PM answer, a miss could cost a run.
    """
    if prior_answers >= settings.answer_limit:
        return GateRefusal(DeclineReason.ANSWER_LIMIT_REACHED, None)
    normalized_question = _normalize(question)
    normalized_answer = _normalize(answer)
    for term in settings.reserved_terms:
        normalized_term = _normalize(term)
        if (
            normalized_term in normalized_question
            or normalized_term in normalized_answer
        ):
            return GateRefusal(DeclineReason.RESERVED_TERM, term)
    return None


def compose_instructions(question: str, answer: str) -> str:
    """The text a resume carries: the question and the answer, two lines (D5)."""
    return f"You asked: {question}\nAnswer: {answer}"
