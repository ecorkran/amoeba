"""The program submission envelope and its parsing.

The same envelope as ``envelope.py``'s with **no project id**: a program
submission is attributed to no project. Parsing reuses that module's decoding,
version and kind checks, and its ``EnvelopeError``, so a program file is refused
for the same reasons and in the same order: version, kind, envelope shape,
payload for the kind. The quarantine reasons that apply are
``unparseable_envelope``, ``unknown_envelope_version``, ``unknown_kind`` and
``invalid_payload``.

:func:`validate_program_envelope` is the single validation path:
``submit_program()`` reaches it through :func:`build_program_envelope` before
writing anything, and the program inbox tenant through
:func:`parse_program_envelope` on every file it drains.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Final

from pydantic import AwareDatetime, BaseModel, ValidationError, field_validator

from amoeba.inbox.envelope import (
    ENVELOPE_KIND_FIELD,
    ENVELOPE_VERSION,
    ENVELOPE_VERSION_FIELD,
    EnvelopeError,
    check_envelope_kind,
    check_envelope_version,
    decode_envelope,
)
from amoeba.inbox.payload_config import MODEL_CONFIG
from amoeba.inbox.program_payloads import PROGRAM_KIND_PAYLOAD_MODELS
from amoeba.store.inbox_models import QuarantineReason
from amoeba.store.paths import validate_path_component
from amoeba.store.program_models import ProgramSubmissionKind

#: The kind values, as plain strings, for checking a raw decoded field.
_PROGRAM_KIND_VALUES: Final = frozenset(kind.value for kind in ProgramSubmissionKind)


class ProgramSubmissionEnvelope(BaseModel):
    """One program submission as written to disk."""

    model_config = MODEL_CONFIG

    envelope_version: int
    id: str
    kind: ProgramSubmissionKind
    submitted_by: str
    submitted_at: AwareDatetime
    payload: dict[str, object]

    @field_validator("id")
    @classmethod
    def _id_is_a_path_component(cls, value: str) -> str:
        # The id names the file; it must not be able to escape the inbox.
        validate_path_component(value, name="id")
        return value


def build_program_envelope(
    *,
    submission_id: str,
    kind: ProgramSubmissionKind,
    submitted_by: str,
    submitted_at: datetime,
    payload: Mapping[str, object],
) -> ProgramSubmissionEnvelope:
    """Assemble an envelope and validate it through the one validation path.

    Raises:
        EnvelopeError: For the same reasons a drained file is quarantined.
    """
    return validate_program_envelope(
        {
            ENVELOPE_VERSION_FIELD: ENVELOPE_VERSION,
            "id": submission_id,
            ENVELOPE_KIND_FIELD: kind.value,
            "submitted_by": submitted_by,
            "submitted_at": submitted_at.isoformat(),
            "payload": dict(payload),
        }
    )


def parse_program_envelope(raw: str | bytes) -> ProgramSubmissionEnvelope:
    """Parse a program submission file's content.

    Raises:
        EnvelopeError: With ``UNPARSEABLE_ENVELOPE`` if it is not a JSON object,
            otherwise as :func:`validate_program_envelope` does.
    """
    return validate_program_envelope(decode_envelope(raw))


def validate_program_envelope(data: Mapping[str, object]) -> ProgramSubmissionEnvelope:
    """Validate a decoded envelope, checking in order and naming one reason.

    Order: version, kind, envelope shape, payload for the kind.

    Raises:
        EnvelopeError: With the reason of the first check that failed.
    """
    check_envelope_version(data)
    check_envelope_kind(data, _PROGRAM_KIND_VALUES)

    try:
        envelope = ProgramSubmissionEnvelope.model_validate(data)
    except ValidationError as error:
        # Specific: a required field is missing or has the wrong type.
        raise EnvelopeError(
            QuarantineReason.UNPARSEABLE_ENVELOPE, str(error)
        ) from error

    try:
        payload = PROGRAM_KIND_PAYLOAD_MODELS[envelope.kind].model_validate(
            envelope.payload
        )
    except ValidationError as error:
        # Specific: the payload does not fit its kind's model; the message names
        # the offending field.
        raise EnvelopeError(QuarantineReason.INVALID_PAYLOAD, str(error)) from error

    # Carry the validated payload as plain JSON values (enums as their strings).
    return envelope.model_copy(update={"payload": payload.model_dump(mode="json")})
