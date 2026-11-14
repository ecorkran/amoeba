"""``changes``: the request and the result (slice 227, D3).

A pair's ``releases`` are ``ReleaseReport`` values, the same shape ``report_release``
returns. ``problems`` reuse ``ReleaseProblem`` with the codes ``malformed`` and
``not_a_member``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

from amoeba.operations.report_release_models import ReleaseProblem, ReleaseReport
from amoeba.operations.set_up_models import FrozenModel
from amoeba.operations.since import parse_since
from amoeba.store.vocabulary import ConsumedMode


class ChangesOutcome(StrEnum):
    """How a ``changes`` call ended."""

    LISTED = "listed"
    REJECTED = "rejected"


class ChangesWarningCode(StrEnum):
    """Things worth saying that do not stop the listing."""

    #: A member or provider id Context Forge's project list does not name.
    NOT_IN_CONTEXT_FORGE = "not_in_context_forge"


class ChangesRequest(BaseModel):
    """What ``changes`` is asked: everything after ``since``. The member is the
    caller's directory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: ISO-8601 with a UTC offset in; the store's UTC text once validated.
    since: StrictStr

    @field_validator("since")
    @classmethod
    def _utc_text(cls, value: str) -> str:
        return parse_since(value)


class MemberRef(FrozenModel):
    """A member as shown; ``name`` is null when Context Forge does not list it."""

    id: str
    name: str | None


class ProviderPair(FrozenModel):
    """One provider of the caller, with the reports the pair's ``consumed`` shows."""

    provider: MemberRef
    consumed: ConsumedMode
    releases: tuple[ReleaseReport, ...]


class ChangesWarning(FrozenModel):
    code: ChangesWarningCode
    #: Names the id Context Forge does not list.
    detail: str


class ChangesResult(FrozenModel):
    """What ``changes`` returns."""

    outcome: ChangesOutcome
    #: The caller's member; null when rejected.
    member: MemberRef | None
    #: The starting time as the store's UTC text; null when the request was malformed.
    since: str | None
    pairs: tuple[ProviderPair, ...]
    problems: tuple[ReleaseProblem, ...]
    warnings: tuple[ChangesWarning, ...]
