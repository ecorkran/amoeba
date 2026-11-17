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
    #: Held on a request this repo sent (242 D2); ends when the request ends.
    WAITING_ON_REQUEST = "waiting_on_request"


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


class MessageKind(StrEnum):
    """What a ``messages`` row is (240 D1). Only requests are written in 240."""

    REQUEST = "request"
    #: A one-way message with no state, written by ``send`` and ``report_release``.
    NOTE = "note"


class RequestState(StrEnum):
    """Where a request stands (240 D4)."""

    OPEN = "open"
    ACCEPTED = "accepted"
    DONE = "done"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

    @classmethod
    def terminal(cls) -> frozenset[RequestState]:
        """The states a request never leaves; the sweep prunes only these."""
        return frozenset({cls.DONE, cls.DECLINED, cls.CANCELLED, cls.EXPIRED})


class DeliveryEvent(StrEnum):
    """What a delivery tells its member: a send, or the state a request reached."""

    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    DONE = "done"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class WakeOutcome(StrEnum):
    """How a wake ended (244 D3); a row that has not ended has none."""

    #: The command ran and exited; the exit code is data (``wakes.exit_code``).
    EXITED = "exited"
    #: The command ran past the wake's deadline and its process group was stopped.
    TIMED_OUT = "timed_out"
    #: The command could not be started: no path, a bad command, a missing script.
    START_FAILED = "start_failed"
    #: The wrapper hit an unexpected error after the command started.
    WRAPPER_FAILED = "wrapper_failed"
