"""Stored standing answers as passage inputs (slice 230, D5).

``answering`` imports nothing from ``store``, so the rows are mapped to its plain
``StandingAnswer`` here.
"""

from __future__ import annotations

from collections.abc import Sequence

from amoeba.answering.standing_passages import StandingAnswer
from amoeba.store.models import StandingAnswerRow


def standing_answers_of(
    rows: Sequence[StandingAnswerRow],
) -> tuple[StandingAnswer, ...]:
    """Each row's id, text and date, in the order given."""
    return tuple(
        StandingAnswer(
            standing_id=row.standing_id, text=row.text, given_at=row.given_at
        )
        for row in rows
    )
