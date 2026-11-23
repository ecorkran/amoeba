"""What the client part gathers, as plain values and as the document that travels
(slice 261, D5).

The client part (``operations.here``) reads the caller's directory and builds one of
these; the hub part parses the document back with :func:`parse_here` and never guesses
a missing value. Everything here is plain data, so the hub imports this module
without reaching the code that runs ``cf`` or ``git``.

A refusal names the key and the field, never a value: an ``origin`` that failed the
check might have held a password.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from amoeba.operations.errors import MALFORMED_CALL, CallRefused
from amoeba.operations.origin import is_reduced_origin

#: The body key the document travels under (``wire.protocol`` names it as well).
HERE_KEY: Final = "here"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HereCaller(_Frozen):
    """The directory's Context Forge project id."""

    project_id: str


class HereCheckout(_Frozen):
    """The project's id, name and path, and the repo's reduced ``origin`` or none."""

    project_id: str
    name: str
    path: str
    origin: str | None

    @field_validator("origin")
    @classmethod
    def _origin_is_reduced(cls, value: str | None) -> str | None:
        if value is not None and not is_reduced_origin(value):
            raise ValueError("not in reduced form")
        return value


class HereNotAProject(_Frozen):
    """The directory is in no Context Forge project; ``not_a_project`` is its text."""

    not_a_project: str


type Here = HereCaller | HereCheckout | HereNotAProject

_NOT_A_PROJECT_FIELD: Final = "not_a_project"


def here_to_document(value: Here) -> dict[str, object]:
    """The JSON-ready document for the body's ``here`` key."""
    return value.model_dump(mode="json")


def _refusal(error: ValidationError) -> CallRefused:
    """A refusal naming each bad field and why, with no input value in it."""
    parts = [
        f"{HERE_KEY}.{'.'.join(str(step) for step in problem['loc'])}: "
        f"{problem['msg'] if problem['type'] == 'value_error' else problem['type']}"
        for problem in error.errors()
    ]
    return CallRefused(MALFORMED_CALL, f"{HERE_KEY} is not usable: {'; '.join(parts)}")


def parse_here(value: object, *, checkout: bool) -> Here:
    """The gathered value in ``value``; ``checkout`` says which shape the call needs.

    Raises:
        CallRefused: ``malformed_call`` when the value is missing, is not an object,
            is the wrong kind for the call, or holds an ``origin`` that is not in
            reduced form.
    """
    if not isinstance(value, dict):
        raise CallRefused(MALFORMED_CALL, f"{HERE_KEY} is missing or is not an object")
    try:
        if _NOT_A_PROJECT_FIELD in value:
            return HereNotAProject.model_validate(value)
        if checkout:
            return HereCheckout.model_validate(value)
        return HereCaller.model_validate(value)
    except ValidationError as error:
        raise _refusal(error) from error
