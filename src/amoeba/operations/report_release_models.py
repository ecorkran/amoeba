"""``report_release``: the request, the stored report and the result (slice 227, D1,
D2).

``ReleaseReport`` is the one ``report`` shape: ``changes`` returns it too. Times are
the store's UTC text. ``ReportReleaseRequest`` is validated here from a raw document,
so the CLI and the MCP layer pass their input through unchanged.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from amoeba.config.user_config import NonBlank
from amoeba.operations.reject_codes import RejectCode, validation_problems
from amoeba.operations.set_up_models import FrozenModel
from amoeba.store.models import Release
from amoeba.store.row_values import encode_timestamp

#: A full git object name: SHA-1 or SHA-256, in hex.
FULL_HASH_LENGTHS: Final = (40, 64)
_HEX: Final = re.compile(r"[0-9a-f]+")


class ReportMode(StrEnum):
    """What a ``report_release`` call does with the member's report for a commit."""

    REPORT = "report"
    CORRECT = "correct"
    WITHDRAW = "withdraw"


class ReportOutcome(StrEnum):
    """How a ``report_release`` call ended."""

    RECORDED = "recorded"
    VERSIONED = "versioned"
    CORRECTED = "corrected"
    UNCHANGED = "unchanged"
    WITHDRAWN = "withdrawn"
    REJECTED = "rejected"


#: Fields a ``withdraw`` call must not carry, and those a writing call must.
_WITHDRAW_FORBIDS: Final = ("version", "changed", "touched")
_WRITE_REQUIRES: Final = ("changed", "touched")


class ReportReleaseRequest(BaseModel):
    """A report to record, correct or withdraw (D1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: ReportMode = ReportMode.REPORT
    commit: StrictStr
    version: NonBlank | None = None
    changed: NonBlank | None = None
    touched: tuple[NonBlank, ...] | None = None

    @field_validator("commit")
    @classmethod
    def _full_hash(cls, value: str) -> str:
        commit = value.strip().lower()
        if len(commit) not in FULL_HASH_LENGTHS or not _HEX.fullmatch(commit):
            raise ValueError(
                "must be a full commit hash of "
                f"{' or '.join(str(length) for length in FULL_HASH_LENGTHS)} hex "
                "characters, not an abbreviation; `git rev-parse` gives a full hash"
            )
        return commit

    @field_validator("version")
    @classmethod
    def _tag_name(cls, value: str | None) -> str | None:
        if value is not None and any(
            character.isspace() or not character.isprintable() for character in value
        ):
            raise ValueError(
                "must be a tag name: no whitespace and no control characters"
            )
        return value

    @field_validator("touched")
    @classmethod
    def _distinct_in_order(
        cls, value: tuple[str, ...] | None
    ) -> tuple[str, ...] | None:
        return None if value is None else tuple(dict.fromkeys(value))

    @model_validator(mode="after")
    def _mode_rules(self) -> Self:
        problems = [
            f"{name} is not allowed in mode {self.mode.value}"
            for name in _WITHDRAW_FORBIDS
            if self.mode is ReportMode.WITHDRAW and getattr(self, name) is not None
        ]
        problems += [
            f"{name} is required in mode {self.mode.value}"
            for name in _WRITE_REQUIRES
            if self.mode is not ReportMode.WITHDRAW and getattr(self, name) is None
        ]
        if self.mode is not ReportMode.WITHDRAW and self.touched == ():
            problems.append("touched needs at least one item")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class ReleaseReport(FrozenModel):
    """A member's report for one commit, as stored."""

    seq: int
    commit: str
    version: str | None
    changed: str
    touched: tuple[str, ...]
    reported_at: str
    versioned_at: str | None

    @classmethod
    def from_release(cls, release: Release) -> ReleaseReport:
        return cls(
            seq=release.seq,
            commit=release.commit,
            version=release.version,
            changed=release.changed,
            touched=release.touched,
            reported_at=encode_timestamp(release.reported_at),
            versioned_at=(
                None
                if release.versioned_at is None
                else encode_timestamp(release.versioned_at)
            ),
        )


class ReleaseProblem(FrozenModel):
    """Why a call was rejected."""

    code: RejectCode
    detail: str


def malformed_problems(error: ValidationError) -> tuple[ReleaseProblem, ...]:
    """The ``malformed`` problems of a request that failed validation, one per error."""
    return tuple(
        ReleaseProblem(code=RejectCode.MALFORMED, detail=detail)
        for detail in validation_problems(error)
    )


class ReportReleaseResult(FrozenModel):
    """What ``report_release`` returns."""

    outcome: ReportOutcome
    #: The Context Forge project id of the caller's member; null when not a member.
    member: str | None
    #: The stored report after the call; null after ``withdrawn`` and on rejection.
    report: ReleaseReport | None
    problems: tuple[ReleaseProblem, ...]
