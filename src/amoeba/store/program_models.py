"""Closed vocabularies and transfer objects for the program store.

Every program vocabulary value is defined here and nowhere else. Like
``models.py``, this module knows nothing about SQL or ``sqlite3``. A test pins
each enum to the ``CHECK`` constraint that lists the same values.

The payload models are the submission wire format and live in
``amoeba.inbox``; ``amoeba.store`` never imports ``amoeba.inbox``. The payload
field names are defined here, beside :class:`ProgramSubmissionKind`, and a test
in ``amoeba.inbox`` pins them to the models.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from amoeba.store.inbox_models import SubmissionOutcome


class ProgramSubmissionKind(StrEnum):
    """What a program submission asks the program store to do.

    Adding a kind is three things: a member here, a payload model in
    ``amoeba.inbox``, and an effect in ``ProgramStore.apply_submission``.
    """

    REGISTER_PROGRAM = "register_program"
    REGISTER_MEMBER = "register_member"


class ConsumptionMode(StrEnum):
    """How one member consumes another: from its source, or from its release."""

    FROM_SOURCE = "from_source"
    FROM_RELEASE = "from_release"


class ProgramRejection(StrEnum):
    """Why a valid program submission was recorded ``rejected``.

    The recorded reason is ``"<code>: <detail>"``; callers branch on the code.
    """

    UNKNOWN_PROGRAM = "unknown_program"
    MEMBER_OF_OTHER_PROGRAM = "member_of_other_program"
    CONCEPT_MEMBER_NOT_MEMBER = "concept_member_not_member"
    OVERRIDE_NOT_MEMBER = "override_not_member"
    #: Reserved: nothing references a member yet (edges and requests will).
    MEMBER_REFERENCED = "member_referenced"


#: A member's requests initiative index lies in the working initiative range
#: (``file-naming-conventions.md``), both bounds inclusive.
REQUESTS_INITIATIVE_MIN: Final = 100
REQUESTS_INITIATIVE_MAX: Final = 799

#: Payload field names, defined once. The payload models in ``amoeba.inbox`` use
#: these as their field names.
PROGRAM_ID: Final = "program_id"
CONCEPT_MEMBER: Final = "concept_member"
CONCEPT_PATH: Final = "concept_path"
MEMBERS: Final = "members"
MEMBER: Final = "member"
MEMBER_PROJECT_ID: Final = "project_id"
MEMBER_REQUESTS_INITIATIVE: Final = "requests_initiative"
MEMBER_CONSUMED: Final = "consumed"
MEMBER_OVERRIDES: Final = "overrides"


@dataclass(frozen=True)
class Program:
    """One program: where its concept document lives, and its member list's age.

    ``updated_at`` advances when the concept location changes, a member is
    added or removed, or any member changes, so it dates the member list.
    """

    program_id: str
    concept_member: str
    concept_path: str
    registered_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Member:
    """One project's membership in a program.

    ``consumed`` is the mode every other member consumes this one by;
    ``overrides`` maps a dependent member's project id to a different mode for
    that one pair. ``updated_at`` advances only when this member's index, mode or
    overrides change.
    """

    program_id: str
    project_id: str
    requests_initiative: int
    consumed: ConsumptionMode
    overrides: Mapping[str, ConsumptionMode]
    registered_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ProgramSubmissionRecord:
    """One applied or rejected program submission.

    ``applied_seq`` is the receiver-assigned order, authoritative unlike
    ``submitted_at``. ``reason`` is ``"<code>: <detail>"`` when rejected.
    """

    applied_seq: int
    id: str
    kind: ProgramSubmissionKind
    submitted_by: str
    submitted_at: datetime
    payload: Mapping[str, object]
    outcome: SubmissionOutcome
    applied_at: datetime
    reason: str | None = None
