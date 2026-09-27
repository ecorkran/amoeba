"""The submission envelope, the per-kind payload models, and parsing.

The envelope is the one externally-authored format in Amoeba, so it is parsed
with pydantic at the boundary. **Unknown extra fields are ignored**; an unknown
``envelope_version`` is refused rather than best-effort parsed.

:func:`validate_envelope` is the single validation path. ``submit()`` reaches
it through :func:`build_envelope` before writing anything, and the tenant
through :func:`parse_envelope` on every file it drains, so a file ``submit()``
would have refused is quarantined for the same reason. Its checks run in a
fixed order, and each failure names exactly one :class:`QuarantineReason`.

Vocabularies and payload keys come from ``amoeba.store`` (models only); this
package never imports a store write path.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Final

from pydantic import (
    AwareDatetime,
    BaseModel,
    ValidationError,
    field_validator,
)

from amoeba.inbox.evidence_payloads import VerdictPayload
from amoeba.inbox.payload_config import MODEL_CONFIG
from amoeba.store.inbox_models import QuarantineReason, SubmissionKind
from amoeba.store.paths import validate_path_component, validate_project_id

#: The only envelope version this code understands.
ENVELOPE_VERSION: Final = 1

#: The envelope field holding the version, read before anything else is.
ENVELOPE_VERSION_FIELD: Final = "envelope_version"
#: The envelope field holding the kind, checked before full validation so an
#: unknown kind is named as such rather than as an unparseable envelope.
ENVELOPE_KIND_FIELD: Final = "kind"


class EnvelopeError(ValueError):
    """A submission failed validation. Carries the one reason it failed."""

    def __init__(self, reason: QuarantineReason, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


# --------------------------------------------------------------------------
# Per-kind payload models. Field names are the keys in ``inbox_models``; a
# test pins the two together.
# --------------------------------------------------------------------------


class CreateProjectPayload(BaseModel):
    """``create_project`` carries nothing: the envelope's project id is it."""

    model_config = MODEL_CONFIG


class ResolutionPayload(BaseModel):
    """Fills one blocked state's slot. Targets the blocked state, not a node."""

    model_config = MODEL_CONFIG

    blocked_state_id: str
    detail: str


class IntentPayload(BaseModel):
    """Something the Runner should act on, optionally about one node."""

    model_config = MODEL_CONFIG

    node_id: str | None = None
    body: dict[str, object]


#: The kind-to-payload-model table, defined once. A kind missing here fails a
#: test, not a user.
KIND_PAYLOAD_MODELS: Final[Mapping[SubmissionKind, type[BaseModel]]] = {
    SubmissionKind.CREATE_PROJECT: CreateProjectPayload,
    SubmissionKind.RESOLUTION: ResolutionPayload,
    SubmissionKind.INTENT: IntentPayload,
    SubmissionKind.VERDICT: VerdictPayload,
}

#: The kind values, as plain strings, for checking a raw decoded field.
_KIND_VALUES: Final = frozenset(kind.value for kind in SubmissionKind)


class SubmissionEnvelope(BaseModel):
    """One submission as written to disk."""

    model_config = MODEL_CONFIG

    envelope_version: int
    id: str
    project_id: str
    kind: SubmissionKind
    submitted_by: str
    submitted_at: AwareDatetime
    payload: dict[str, object]

    @field_validator("id")
    @classmethod
    def _id_is_a_path_component(cls, value: str) -> str:
        # The id names the file; it must not be able to escape the inbox.
        validate_path_component(value, name="id")
        return value


def build_envelope(
    *,
    submission_id: str,
    project_id: str,
    kind: SubmissionKind,
    submitted_by: str,
    submitted_at: datetime,
    payload: Mapping[str, object],
) -> SubmissionEnvelope:
    """Assemble an envelope and validate it through :func:`validate_envelope`.

    Raises:
        EnvelopeError: For the same reasons a drained file is quarantined.
    """
    return validate_envelope(
        {
            ENVELOPE_VERSION_FIELD: ENVELOPE_VERSION,
            "id": submission_id,
            "project_id": project_id,
            ENVELOPE_KIND_FIELD: kind.value,
            "submitted_by": submitted_by,
            "submitted_at": submitted_at.isoformat(),
            "payload": dict(payload),
        }
    )


def parse_envelope(raw: str | bytes) -> SubmissionEnvelope:
    """Parse a submission file's content.

    Raises:
        EnvelopeError: With ``UNPARSEABLE_ENVELOPE`` if it is not a JSON
            object, otherwise as :func:`validate_envelope` does.
    """
    try:
        data: object = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        # Specific: the content is not JSON — a truncated or foreign file.
        raise EnvelopeError(
            QuarantineReason.UNPARSEABLE_ENVELOPE, f"not JSON: {error}"
        ) from error
    if not isinstance(data, dict):
        raise EnvelopeError(QuarantineReason.UNPARSEABLE_ENVELOPE, "not a JSON object")
    return validate_envelope(data)  # pyright: ignore[reportUnknownArgumentType]


def validate_envelope(data: Mapping[str, object]) -> SubmissionEnvelope:
    """Validate a decoded envelope, checking in order and naming one reason.

    Order: version, kind, envelope shape, project id, payload for the kind.

    Raises:
        EnvelopeError: With the reason of the first check that failed.
    """
    version = data.get(ENVELOPE_VERSION_FIELD)
    # An exact int: ``True == 1`` and ``1.0 == 1`` must not pass as version 1.
    if type(version) is not int or version != ENVELOPE_VERSION:
        raise EnvelopeError(
            QuarantineReason.UNKNOWN_ENVELOPE_VERSION,
            f"expected {ENVELOPE_VERSION}, got {version!r}",
        )

    kind = data.get(ENVELOPE_KIND_FIELD)
    # A string first: an unhashable value must be named, not crash the check.
    if not isinstance(kind, str) or kind not in _KIND_VALUES:
        raise EnvelopeError(QuarantineReason.UNKNOWN_KIND, f"kind {kind!r}")

    try:
        envelope = SubmissionEnvelope.model_validate(data)
    except ValidationError as error:
        # Specific: a required field is missing or has the wrong type.
        raise EnvelopeError(
            QuarantineReason.UNPARSEABLE_ENVELOPE, str(error)
        ) from error

    try:
        validate_project_id(envelope.project_id)
    except ValueError as error:
        # Specific: the one project-id rule, reused rather than re-implemented.
        raise EnvelopeError(QuarantineReason.INVALID_PROJECT_ID, str(error)) from error

    try:
        payload = KIND_PAYLOAD_MODELS[envelope.kind].model_validate(envelope.payload)
    except ValidationError as error:
        # Specific: the payload does not fit its kind's model.
        raise EnvelopeError(QuarantineReason.INVALID_PAYLOAD, str(error)) from error

    # Carry the validated payload, not the raw one: unknown extra keys drop.
    return envelope.model_copy(update={"payload": payload.model_dump()})
