"""``standing`` and ``withdraw``: the requests, results and outcome vocabularies
(slice 230, D2, D3).

The request models are validated by the operations from a raw document, so the CLI
and the MCP layer pass their input through unchanged and both doors give the same
``rejected`` result.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StrictInt, model_validator

from amoeba.operations.set_up_models import FrozenModel, NonBlankText
from amoeba.store.vocabulary import StandingReach


class StandingRequest(FrozenModel):
    """What ``standing`` is asked: the PM's ruling and, if limited, its reach."""

    #: The PM's words, as given; never composed by the agent.
    text: NonBlankText
    #: Limits the ruling to one program's members.
    program: NonBlankText | None = None
    #: Limits the ruling to one member: a Context Forge project name or id.
    member: NonBlankText | None = None

    @model_validator(mode="after")
    def _one_reach(self) -> Self:
        if self.program is not None and self.member is not None:
            raise ValueError("program and member cannot both be given")
        return self


class StandingOutcome(StrEnum):
    """How a ``standing`` call ended."""

    GIVEN = "given"
    #: An active row already has the same text and reach; nothing written (D2).
    UNCHANGED = "unchanged"
    REJECTED = "rejected"


class StandingRejection(StrEnum):
    """Why a ``standing`` call was rejected."""

    MALFORMED = "malformed"
    NO_SUCH_PROGRAM = "no_such_program"
    #: ``cf`` does not know the name, or the project is not an active member.
    NO_SUCH_MEMBER = "no_such_member"
    #: With it, the standing answers reaching some member would render past
    #: ``passages_max_chars``, so no answering run there could be sent them.
    TOO_LONG = "too_long"


class StandingResult(FrozenModel):
    """What ``standing`` returns. Fields that do not apply are null or empty."""

    outcome: StandingOutcome
    rejection: StandingRejection | None = None
    #: The row given, or the matching active row; null when rejected.
    standing_id: int | None = None
    reach: StandingReach | None = None
    program: str | None = None
    #: The member's project id, for reach ``member``.
    member: str | None = None
    problems: tuple[str, ...] = ()

    @classmethod
    def rejected(
        cls, rejection: StandingRejection, problems: tuple[str, ...]
    ) -> StandingResult:
        return cls(
            outcome=StandingOutcome.REJECTED, rejection=rejection, problems=problems
        )


class WithdrawRequest(FrozenModel):
    """What ``withdraw`` is asked: which standing answer, and why."""

    standing_id: Annotated[StrictInt, Field(gt=0)]
    reason: NonBlankText


class WithdrawOutcome(StrEnum):
    """How a ``withdraw`` call ended."""

    WITHDRAWN = "withdrawn"
    #: The row was already withdrawn; nothing changed (D3).
    UNCHANGED = "unchanged"
    REJECTED = "rejected"


class WithdrawRejection(StrEnum):
    """Why a ``withdraw`` call was rejected."""

    NO_SUCH_STANDING_ANSWER = "no_such_standing_answer"
    MALFORMED = "malformed"


class WithdrawResult(FrozenModel):
    """What ``withdraw`` returns. Fields that do not apply are null or empty."""

    outcome: WithdrawOutcome
    rejection: WithdrawRejection | None = None
    standing_id: int | None = None
    problems: tuple[str, ...] = ()
