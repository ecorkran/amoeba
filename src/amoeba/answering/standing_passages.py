"""The ``standing_answer`` passages: the PM's rulings given ahead of time (slice 230,
D5).

Plain fields in, so ``answering`` imports nothing from ``store``. The passages follow
the request passage and come before PM answers, in id order, and are never trimmed:
a ruling the PM gave must not be dropped quietly to make room. A set that is too
large is ``sources_too_large``, and its detail gives both shares.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from amoeba.answering.passage_types import Passage, PassageKind

#: A standing answer passage's ``source`` is this and the row's id. ``decisions``
#: names a cited passage's kind from it, because the passage record keeps no kind.
STANDING_SOURCE_PREFIX: Final = "standing:"
#: The whole of such a source: the prefix and a positive id, nothing else.
_STANDING_SOURCE: Final = re.compile(rf"{re.escape(STANDING_SOURCE_PREFIX)}[1-9]\d*")


def is_standing_source(source: str) -> bool:
    """Whether ``source`` is exactly a standing answer passage's ``standing:<id>``."""
    return _STANDING_SOURCE.fullmatch(source) is not None


@dataclass(frozen=True)
class StandingAnswer:
    """One standing answer reaching the member, as the store gave it."""

    standing_id: int
    text: str
    given_at: datetime


def standing_passage(answer: StandingAnswer, number: int) -> Passage:
    """The passage of one standing answer, numbered ``P<number>``."""
    return Passage(
        id=f"P{number}",
        kind=PassageKind.STANDING_ANSWER,
        source=f"{STANDING_SOURCE_PREFIX}{answer.standing_id}",
        date=answer.given_at,
        text=answer.text,
        question=None,
        slice_label=None,
        question_id=None,
        member=None,
    )


def add_standing_passages(
    kept: Sequence[Passage], answers: Sequence[StandingAnswer]
) -> list[Passage]:
    """``kept`` with each standing answer appended in id order, numbered after it."""
    ordered = sorted(answers, key=lambda answer: answer.standing_id)
    return [
        *kept,
        *(
            standing_passage(answer, len(kept) + position)
            for position, answer in enumerate(ordered, start=1)
        ),
    ]


def too_large_detail(base_chars: int, standing_chars: int, max_chars: int) -> str:
    """``sources_too_large``'s detail: both shares and the limit, so the PM can tell
    whether to withdraw standing answers or raise the cap."""
    return (
        f"rules, plan, program and request passages are {base_chars} characters and "
        f"standing answers {standing_chars}; the limit is {max_chars}"
    )
