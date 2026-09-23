"""The two sidecar formats, defined once for the writer and every reader.

``.reason.json`` sits beside a quarantined file; ``.attempts.json`` beside a
file in ``new/`` whose apply has failed, and travels with it to ``failed/``.
The tenant writes both; the listings read both.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import AwareDatetime, BaseModel, ConfigDict, PositiveInt, ValidationError

from amoeba.store.inbox_models import QuarantineReason

_MODEL_CONFIG = ConfigDict(extra="ignore", frozen=True)


class ReasonSidecar(BaseModel):
    """Why a file could not be attributed to an open project store."""

    model_config = _MODEL_CONFIG

    reason: QuarantineReason
    detail: str
    quarantined_at: AwareDatetime


class AttemptsSidecar(BaseModel):
    """How many consecutive applies of a file have failed, and the last error."""

    model_config = _MODEL_CONFIG

    attempts: PositiveInt
    last_error: str
    last_failed_at: AwareDatetime


class SidecarError(ValueError):
    """A sidecar is missing or cannot be read. Reported, never defaulted."""


def read_sidecar[SidecarT: (ReasonSidecar, AttemptsSidecar)](
    path: Path, model: type[SidecarT]
) -> SidecarT:
    """Read one sidecar.

    Raises:
        SidecarError: If the file is missing, unreadable, or malformed.
    """
    try:
        return model.model_validate_json(path.read_bytes())
    except FileNotFoundError as error:
        # Specific: no sidecar was written, e.g. a file moved by hand.
        raise SidecarError(f"{path.name} is missing") from error
    except (OSError, ValidationError) as error:
        # Specific: the sidecar exists but cannot be read or parsed.
        raise SidecarError(f"{path.name} is unreadable: {error}") from error
