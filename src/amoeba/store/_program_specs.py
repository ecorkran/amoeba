"""A program submission's payload as typed values, for the apply transaction.

``amoeba.store`` takes plain, already-validated values (the payload models live
in ``amoeba.inbox``); this reads them into frozen dataclasses. A payload that is
not the shape its kind promises raises ``ValueError`` before anything is written.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from amoeba.store.program_models import (
    CONCEPT_MEMBER,
    CONCEPT_PATH,
    MEMBER,
    MEMBER_CONSUMED,
    MEMBER_OVERRIDES,
    MEMBER_PROJECT_ID,
    MEMBER_REQUESTS_INITIATIVE,
    MEMBERS,
    PROGRAM_ID,
    ConsumptionMode,
)


@dataclass(frozen=True)
class MemberSpec:
    """One member as a submission states it."""

    project_id: str
    requests_initiative: int
    consumed: ConsumptionMode
    overrides: Mapping[str, ConsumptionMode]


@dataclass(frozen=True)
class ProgramSpec:
    """A ``register_program`` body."""

    program_id: str
    concept_member: str
    concept_path: str
    members: tuple[MemberSpec, ...]


@dataclass(frozen=True)
class MemberRegistration:
    """A ``register_member`` body."""

    program_id: str
    member: MemberSpec


def _field(source: Mapping[str, object], name: str, kind: type) -> object:
    value = source.get(name)
    if not isinstance(value, kind) or isinstance(value, bool):
        raise ValueError(f"payload field {name!r} must be {kind.__name__}: {value!r}")
    return value


def _member(raw: object) -> MemberSpec:
    if not isinstance(raw, Mapping):
        raise ValueError(f"a member must be an object: {raw!r}")
    source = cast("Mapping[str, object]", raw)
    overrides = _field(source, MEMBER_OVERRIDES, Mapping)
    return MemberSpec(
        project_id=str(_field(source, MEMBER_PROJECT_ID, str)),
        requests_initiative=cast(
            "int", _field(source, MEMBER_REQUESTS_INITIATIVE, int)
        ),
        consumed=ConsumptionMode(str(_field(source, MEMBER_CONSUMED, str))),
        overrides={
            str(dependent): ConsumptionMode(str(mode))
            for dependent, mode in cast("Mapping[object, object]", overrides).items()
        },
    )


def parse_program(payload: Mapping[str, object]) -> ProgramSpec:
    """Read a ``register_program`` payload."""
    members = _field(payload, MEMBERS, list)
    return ProgramSpec(
        program_id=str(_field(payload, PROGRAM_ID, str)),
        concept_member=str(_field(payload, CONCEPT_MEMBER, str)),
        concept_path=str(_field(payload, CONCEPT_PATH, str)),
        members=tuple(_member(raw) for raw in cast("Sequence[object]", members)),
    )


def parse_member_registration(payload: Mapping[str, object]) -> MemberRegistration:
    """Read a ``register_member`` payload."""
    return MemberRegistration(
        program_id=str(_field(payload, PROGRAM_ID, str)),
        member=_member(payload.get(MEMBER)),
    )
