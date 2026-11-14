"""The store's closed vocabularies; a test pins each schema ``CHECK`` list to them.

``AnsweredBy`` lives in ``answering.values``; the rest are here.
"""

from __future__ import annotations

from enum import StrEnum


class ConsumedMode(StrEnum):
    """Which of a provider's reports a consumer sees."""

    FROM_SOURCE = "from_source"
    FROM_RELEASE = "from_release"


class RulesFrom(StrEnum):
    """Where a member's rules come from (229 D7)."""

    #: The member's own ``rules_paths`` entries; an empty list means no rules.
    NAMED = "named"
    #: The config's ``default_rules_paths``, read at answering time.
    CONFIG_DEFAULT = "config_default"


class QuestionState(StrEnum):
    """Where a claimed question stands."""

    CLAIMED = "claimed"
    ANSWERED = "answered"
    WAITING_ON_PM = "waiting_on_pm"
    #: Ended without an answer to deliver (228 D3); ``answer`` reopens it.
    CLOSED = "closed"


class ClosedReason(StrEnum):
    """Why a question was closed."""

    #: The PM, or an agent for the PM, ran ``dismiss``.
    DISMISSED = "dismissed"
    #: The run left that pause, or finished, so nobody can answer it.
    RUN_MOVED_ON = "run_moved_on"
    #: Squadron no longer knows the run.
    RUN_GONE = "run_gone"


class Door(StrEnum):
    """Which interface carried a call: the command line or the MCP server (226 D11).

    Recorded beside each PM answer. Defined here, where ``answers.via`` is pinned,
    and re-exported by ``operations.names`` for the doors.
    """

    CLI = "cli"
    MCP = "mcp"


class ResumeOutcome(StrEnum):
    """What happened when an answer was handed back to the paused run."""

    RESUMED = "resumed"
    REFUSED = "refused"
    NOT_DELIVERED = "not_delivered"
