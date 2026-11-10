"""The store's closed vocabularies; a test pins each schema ``CHECK`` list to them.

``AnsweredBy`` lives in ``answering.values``; the rest are here.
"""

from __future__ import annotations

from enum import StrEnum


class ConsumedMode(StrEnum):
    """Which of a provider's reports a consumer sees."""

    FROM_SOURCE = "from_source"
    FROM_RELEASE = "from_release"


class QuestionState(StrEnum):
    """Where a claimed question stands."""

    CLAIMED = "claimed"
    ANSWERED = "answered"
    WAITING_ON_PM = "waiting_on_pm"


class ResumeOutcome(StrEnum):
    """What happened when an answer was handed back to the paused run."""

    RESUMED = "resumed"
    REFUSED = "refused"
    NOT_DELIVERED = "not_delivered"
