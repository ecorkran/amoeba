"""Check vocabularies, record types, the standing function, and the payload keys.

A check records what it examined (D5): ``examined_count`` says how many things
the check looked at, and the standing is derived from it on read, never stored.
A validator that exits 0 having examined nothing is ``vacuous``, not ``passed``.

Every check word lives here, as in ``journal_models.py`` and
``evidence_models.py``. This module knows nothing about SQL, ``sqlite3``, or
pydantic. The ``check`` submission's payload keys are defined once below;
``amoeba.inbox``'s ``CheckPayload`` uses them as its field names and a test pins
the two. A malformed payload raises ``ValueError``: envelope validation upstream
should have made that impossible.

``ProgressInput`` has no record type: progress records are write-only (D6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final, cast

from amoeba.store.evidence_models import Provenance, RecordSource


class CheckOutcome(StrEnum):
    """What the check itself reported."""

    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"


class CheckStanding(StrEnum):
    """What a recorded check is worth, derived by :func:`check_standing`."""

    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"
    UNATTESTED = "unattested"
    VACUOUS = "vacuous"


class ProgressKind(StrEnum):
    """The two SQ 280 record types with no other home (D6)."""

    TASK_PROGRESS = "task_progress"
    DEVLOG = "devlog"


def check_standing(outcome: CheckOutcome, examined_count: int | None) -> CheckStanding:
    """The one standing rule, checked top to bottom as the D5 table orders it."""
    if outcome is CheckOutcome.ERRORED:
        return CheckStanding.ERRORED
    if examined_count is None:
        return CheckStanding.UNATTESTED
    if examined_count == 0:
        return CheckStanding.VACUOUS
    return CheckStanding(outcome.value)


@dataclass(frozen=True, kw_only=True)
class CheckInput:
    """One check result. ``examined_count`` has no default: null says "not reported"."""

    id: str
    node_id: str
    name: str
    outcome: CheckOutcome
    examined_count: int | None
    provenance: Provenance
    examined: Mapping[str, object] | None = None
    baseline_ref: str | None = None


@dataclass(frozen=True, kw_only=True)
class CheckRecord(CheckInput):
    """A recorded check. ``recorded_seq`` is arrival order."""

    project_id: str
    recorded_seq: int
    recorded_at: datetime

    @property
    def standing(self) -> CheckStanding:
        return check_standing(self.outcome, self.examined_count)


@dataclass(frozen=True, kw_only=True)
class ProgressInput:
    """One progress record; ``content`` is opaque until a consumer defines it."""

    id: str
    node_id: str
    progress_kind: ProgressKind
    content: Mapping[str, object]
    provenance: Provenance


CHECK_NODE_ID: Final = "node_id"
CHECK_NAME: Final = "name"
CHECK_OUTCOME: Final = "outcome"
CHECK_EXAMINED_COUNT: Final = "examined_count"
CHECK_EXAMINED: Final = "examined"
CHECK_BASELINE_REF: Final = "baseline_ref"
CHECK_UPSTREAM: Final = "upstream"
CHECK_UPSTREAM_VERSION: Final = "upstream_version"
CHECK_SOURCE: Final = "source"
CHECK_SOURCE_PATH: Final = "source_path"

#: Every key of the ``check`` payload, for the test pinning ``CheckPayload``.
CHECK_PAYLOAD_KEYS: Final = frozenset(
    {
        CHECK_NODE_ID,
        CHECK_NAME,
        CHECK_OUTCOME,
        CHECK_EXAMINED_COUNT,
        CHECK_EXAMINED,
        CHECK_BASELINE_REF,
        CHECK_UPSTREAM,
        CHECK_UPSTREAM_VERSION,
        CHECK_SOURCE,
        CHECK_SOURCE_PATH,
    }
)


def _malformed(key: str, value: object, expected: str) -> ValueError:
    return ValueError(f"check payload {key!r} must be {expected}: {value!r}")


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise _malformed(key, value, "a string")
    return value


def _optional_text(payload: Mapping[str, object], key: str) -> str | None:
    return None if payload.get(key) is None else _text(payload, key)


def _examined_count(payload: Mapping[str, object]) -> int | None:
    # No default: a missing key is not "not reported"; the submitter says null.
    if CHECK_EXAMINED_COUNT not in payload:
        raise _malformed(CHECK_EXAMINED_COUNT, None, "present (an integer or null)")
    value = payload[CHECK_EXAMINED_COUNT]
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise _malformed(CHECK_EXAMINED_COUNT, value, "an integer or null")
    return value


def _examined(payload: Mapping[str, object]) -> Mapping[str, object] | None:
    value = payload.get(CHECK_EXAMINED)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise _malformed(CHECK_EXAMINED, value, "an object or null")
    return cast(Mapping[str, object], value)


def _member[VocabularyT: (CheckOutcome, RecordSource)](
    payload: Mapping[str, object], key: str, vocabulary: type[VocabularyT]
) -> VocabularyT:
    value = payload.get(key)
    if not isinstance(value, str):
        raise _malformed(key, value, f"a {vocabulary.__name__}")
    try:
        return vocabulary(value)
    except ValueError:
        raise _malformed(key, value, f"a {vocabulary.__name__}") from None


def check_from_payload(submission_id: str, payload: Mapping[str, object]) -> CheckInput:
    """Build the ``CheckInput`` a submission describes; its id is the record id."""
    return CheckInput(
        id=submission_id,
        node_id=_text(payload, CHECK_NODE_ID),
        name=_text(payload, CHECK_NAME),
        outcome=_member(payload, CHECK_OUTCOME, CheckOutcome),
        examined_count=_examined_count(payload),
        examined=_examined(payload),
        baseline_ref=_optional_text(payload, CHECK_BASELINE_REF),
        provenance=Provenance(
            upstream=_text(payload, CHECK_UPSTREAM),
            upstream_version=_text(payload, CHECK_UPSTREAM_VERSION),
            source=_member(payload, CHECK_SOURCE, RecordSource),
            source_path=_optional_text(payload, CHECK_SOURCE_PATH),
        ),
    )
